"""The editing UI: a plan of the page, not a list of tables.

An editor thinks « the figures band sits too high », never « table Section,
column position ». So the entry point is the page in miniature: reorder, show
or hide, then drill into a section.

Never embeddable, and never public: every view here denies framing outright
and requires an account that Authentik put in the editing group.

The request-free storage helpers a list's own editing screen reads and
writes through — `list_values`, `save_list`, and the guards around them —
live in `accueil.lists`: they know nothing about HTTP and raise `Http404`
rather than redirect. This module is the HTTP wrapper around them, plus the
concurrency and unreadable-override guards a *view* needs (a flash message,
a redirect) and the two decorators every screen here shares.
"""

import copy
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_deny
from django.views.decorators.csp import csp_override
from django.views.decorators.http import require_POST

from accueil.forms import item_form_class, section_form_class
from accueil.lists import _digest, _list_field, _override_is_unreadable, list_values, save_list
from accueil.models import Page, Section
from accueil.previews import section_lists
from accueil.sections import Illustration, ListField, registry


def may_publish(user):
    return user.is_superuser


# `staff_member_required` would do, but it hard-codes a redirect to the admin
# login, which is not always mounted and is the wrong door once Authentik is on.
# `user_passes_test` honours settings.LOGIN_URL.
editor_required = user_passes_test(lambda user: user.is_active and user.is_staff)


def editor_view(*, post_only=False):
    """Everything the editing UI needs, in the order that keeps it closed.

    The public page is meant to be framed; this one must not be, so framing is
    denied explicitly rather than inherited. `require_POST` goes *inside* the
    header decorators: outside, its 405 would escape them and fall back to the
    public, embeddable policy.
    """

    def decorate(view):
        if post_only:
            view = require_POST(view)
        for decorator in (
            editor_required,
            xframe_options_deny,
            # Replaces the site-wide policy rather than merging with it: any
            # directive added to SECURE_CSP must be repeated here.
            csp_override({"frame-ancestors": ["'none'"]}),
        ):
            view = decorator(view)
        return view

    return decorate


def _plan(page):
    """Sections in page order, paired with what the code declares about them."""
    declared = {section_type.key: section_type for section_type in registry.types()}
    plan = []
    for section in page.sections.all():
        section_type = declared.get(section.kind)
        plan.append(
            {
                "row": section,
                "name": section_type.label if section_type else section.kind,
                "known": section_type is not None,
                "customised": bool(section.content),
                "summary": _summary(section_type, section) if section_type else "type absent du code",
                "url": reverse("edition:section", args=[section.pk]),
            }
        )
    return plan


def _summary(section_type, section):
    """One line describing the section by its content, not by its type.

    Counts each list under its declared label ("Témoignages"), the same
    label the section screen's own board carries for it — never the field's
    identifier ("quotes"), which an editor never reads (CLAUDE.md).
    """
    content = section_type(section.content).content
    title = content.get("title") or content.get("kicker") or ""
    counts = []
    for name, value in content.items():
        if not (isinstance(value, list) and value):
            continue
        field = section_type.Form.base_fields.get(name)
        label = getattr(field, "label", None) or name
        counts.append(f"{len(value)} {label}")
    parts = [f"« {title} »"] if title else []
    parts += counts
    return " · ".join(parts)


@editor_view()
def plan(request):
    page = Page.objects.filter(slug="accueil").first()
    return render(
        request,
        "edition/plan.html",
        {
            "page": page,
            "plan": _plan(page) if page else [],
            "may_publish": may_publish(request.user),
        },
    )


@editor_view(post_only=True)
def move(request, pk):
    """Swap a section with its neighbour. A form post, so it works without JS."""
    section = get_object_or_404(Section, pk=pk, page__slug="accueil")
    direction = request.POST.get("direction")
    neighbours = Section.objects.filter(page=section.page)
    neighbour = (
        neighbours.filter(position__lt=section.position).order_by("-position").first()
        if direction == "up"
        else neighbours.filter(position__gt=section.position).order_by("position").first()
    )
    if neighbour is not None:
        section.position, neighbour.position = neighbour.position, section.position
        # Saved through the model so the page cache is dropped at once.
        neighbour.save(update_fields=["position"])
        section.save(update_fields=["position"])
    return redirect("edition:plan")


@editor_view(post_only=True)
def toggle(request, pk):
    section = get_object_or_404(Section, pk=pk, page__slug="accueil")
    section.active = not section.active
    section.save(update_fields=["active"])
    return redirect("edition:plan")


def _declared(kind):
    return {section_type.key: section_type for section_type in registry.types()}.get(kind)


def _list_context(pk, name):
    """The section, its declared type and the declared `ListField` for `name`.

    404s on a missing section, a section whose kind is no longer in the code,
    or a name that is not a declared list — the same three ways a POST to a
    list operation can be misrouted.
    """
    row = get_object_or_404(Section, pk=pk, page__slug="accueil")
    section_type = _declared(row.kind)
    if section_type is None:
        raise Http404(f"« {row.kind} » n'existe plus dans le code.")
    field = _list_field(section_type, name)
    return row, section_type, field


def _refuse_if_unreadable(request, row, section_type, name, *, detail="impossible d'agir dessus depuis cet écran."):
    """Redirect to the section, with a flash message, if `name`'s stored
    override no longer validates — needed on every screen that could mutate
    a list: acting on `list_values`' silent fallback to the code default
    would replace an editor's unreadable-but-real override with content
    built from the code, with nothing to say so.

    `detail` completes the sentence for the caller's own operation: `_apply`
    refuses an operation on an item it never shows, while `item`/`item_add`
    refuse opening or saving a whole form — the generic "agir dessus" reads
    oddly for either of those, so each call site says what it was actually
    trying to do.
    """
    if not _override_is_unreadable(row, section_type, name):
        return None
    messages.error(
        request,
        f"Cette liste est illisible : une modification qu'elle contient n'est plus reconnue par le "
        f"code, et {detail} Rien n'a été modifié.",
    )
    return redirect("edition:section", pk=row.pk)


def _refuse_if_stale(request, row, values, *, digest=None):
    """Redirect to the section, with a flash message, unless the posted
    `token` matches `_digest(values)`.

    Shared verbatim by `_apply` and `item`/`item_add` — this is the one
    editor-facing sentence, and the one guard, that must not drift between
    the screens it protects: each of them turns a list that changed
    underneath an editor into a refusal, rather than a silent, positional
    overwrite of whatever is there now.

    `digest` lets a caller that already computed it once (`item`, which also
    needs it to render the next form) pass it straight in, rather than hash
    `values` a second time for the same request.
    """
    if request.POST.get("token") == (digest if digest is not None else _digest(values)):
        return None
    messages.error(
        request,
        "Cette liste a changé depuis l'affichage de la page. Rien n'a été modifié : rechargez et réessayez.",
    )
    return redirect("edition:section", pk=row.pk)


def _apply(request, pk, name, change, done, then=None):
    """Apply one operation to a list, and say so — success or refusal alike.

    `done` is the sentence shown once it applied. Each operation passes its
    own: an editor who deletes a testimonial must not be told it was updated,
    and this branch's whole subject is not destroying an editor's work by
    accident.

    `then` builds where a *successful* operation lands. A refusal always returns
    to the section: that is where the message and the board are.

    Two guards run before `change` ever sees the list, in addition to the
    whole-list validation `save_list` already does: an override that no
    longer validates is left untouched (`_refuse_if_unreadable`), and the
    POST must carry a `token` matching `_digest` of the list as read here, or
    the operation is refused as stale (`_refuse_if_stale`). The token is
    required, not optional: were it optional, a template that forgot to send
    it would simply never trigger the guard, rather than fail loudly with
    buttons that do not work.
    """
    row, section_type, field = _list_context(pk, name)
    refusal = _refuse_if_unreadable(request, row, section_type, name)
    if refusal is not None:
        return refusal

    values = list_values(row, section_type, name, field)
    refusal = _refuse_if_stale(request, row, values)
    if refusal is not None:
        return refusal

    try:
        change(values)
        save_list(row, section_type, name, values, field)
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return redirect("edition:section", pk=pk)

    messages.success(request, done)
    return then(pk) if then else redirect("edition:section", pk=pk)


@editor_view(post_only=True)
def item_duplicate(request, pk, name, index):
    # Structurally unusable on a list declaring `unique` (`profiles`, on
    # `slug`): every duplicate collides with the item it copies and is
    # refused by `save_list`'s whole-list validation, cleanly and with
    # nothing written. `item_add` is the only way such a list grows.
    def change(values):
        _check_index(values, index)
        values.insert(index + 1, copy.deepcopy(values[index]))

    # Straight to the copy: duplicating is how an editor starts a new item from
    # an old one, so the next thing they want is to change it.
    return _apply(
        request,
        pk,
        name,
        change,
        "Élément dupliqué.",
        then=lambda pk: redirect("edition:item", pk=pk, name=name, index=index + 1),
    )


@editor_view(post_only=True)
def item_delete(request, pk, name, index):
    def change(values):
        _check_index(values, index)
        values.pop(index)

    return _apply(request, pk, name, change, "Élément supprimé.")


@editor_view(post_only=True)
def item_move(request, pk, name, index):
    return _apply(request, pk, name, _swap(index, request.POST.get("direction")), "Élément déplacé.")


def _swap(index, direction):
    """Build a move, as a plain list mutation — no `request` in here.

    An unrecognised or absent `direction` is a no-op, not a downward move:
    only "up" and "down" carry meaning. Landing past either end of the list
    is a no-op too, and that is only correct for a screen that withholds the
    button there in the first place — the contract the template must honour.
    """
    other = {"up": index - 1, "down": index + 1}.get(direction)

    def change(values):
        _check_index(values, index)
        if other is not None and 0 <= other < len(values):
            values[index], values[other] = values[other], values[index]

    return change


def _check_index(values, index):
    if not 0 <= index < len(values):
        raise Http404("Cet élément n'existe pas.")


UPLOADS_BLOCK_REASON = (
    "Impossible d'ajouter un élément ici : cette liste exige une image, "
    "et le téléversement n'est pas configuré pour le moment."
)


def _blocks_creation_without_uploads(field):
    """True when adding a new item is structurally impossible right now.

    The item form declares a required `Illustration` with no `initial`
    (`figures.Indicator.image`, `search.Card.image`: each real item has its
    own picture, so there is no sane default to seed a new one with — see
    `Illustration`'s own docstring), and uploads are not configured
    (`settings.UPLOADS_ENABLED`, false whenever no bucket is set, which is
    the default locally and on a deploy without one). Without this check the
    add screen renders what looks like an ordinary form — `IllustrationWidget`
    quietly omits the file input it has nothing to offer (see its template)
    — and only fails on submit, with "Ce champ est obligatoire." pointing at
    a control that was never on the page.
    """
    if settings.UPLOADS_ENABLED:
        return False
    return any(
        isinstance(declared, Illustration) and declared.required and declared.initial is None
        for declared in field.item_form.base_fields.values()
    )


@editor_view()
def item(request, pk, name, index):
    """Edit one item of a list through the fields its item form declares.

    Carries the same concurrency token `_apply` requires, and for the same
    reason: `attempt[index] = form.cleaned_data` is a positional write. If
    the list shifted between the GET that rendered this form and the POST —
    an item removed or reordered elsewhere — the editor who believes they
    are saving item "B" would otherwise silently overwrite whatever now sits
    at that index, with a success redirect and nothing to say a *different*
    item was destroyed. The token is embedded as a hidden input by the
    template, so it rides the GET → POST round trip with no JavaScript,
    exactly as `_apply`'s buttons already do.
    """
    row, section_type, field = _list_context(pk, name)
    detail = (
        "impossible d'enregistrer cet élément depuis cet écran."
        if request.method == "POST"
        else "impossible d'ouvrir cet élément depuis cet écran."
    )
    refusal = _refuse_if_unreadable(request, row, section_type, name, detail=detail)
    if refusal is not None:
        return refusal

    values = list_values(row, section_type, name, field)
    values_digest = _digest(values)
    form_class = item_form_class(field)

    if request.method == "POST":
        # Checked before `_check_index`, deliberately: a stale token already
        # means this POST cannot be trusted to describe the list as it now
        # stands, including when the list has since shrunk enough that
        # `index` would 404 on its own. Refusing as stale here, rather than
        # as not-found, is what keeps this case readable: "the list changed"
        # is true and actionable, "this element doesn't exist" would not be,
        # for an editor who watched it exist a moment ago.
        refusal = _refuse_if_stale(request, row, values, digest=values_digest)
        if refusal is not None:
            return refusal
        _check_index(values, index)
        form = form_class(request.POST, request.FILES)
        if form.is_valid():
            # A copy, not a mutation of `values` in place: `values_digest`
            # above must still describe what is actually stored if this save
            # is refused below (a collision with `unique`, say), or the next
            # attempt's token would be checked against content that was
            # never written — a false "list changed" for a list that did not.
            attempt = list(values)
            attempt[index] = form.cleaned_data
            try:
                save_list(row, section_type, name, attempt, field)
            except ValidationError as error:
                messages.error(request, error.messages[0])
            else:
                messages.success(request, "Élément mis à jour.")
                return redirect("edition:section", pk=pk)
    else:
        _check_index(values, index)
        form = form_class(initial=values[index])

    return render(
        request,
        "edition/item.html",
        {
            "row": row,
            "section_type": section_type,
            "field": field,
            "index": index,
            "form": form,
            "token": values_digest,
            "creating": False,
        },
    )


@editor_view()
def item_add(request, pk, name):
    """Append a new item, built and validated through its own form.

    Never inserted directly as an empty dict: a list whose item fields are
    required (`search.Card`, most of them) would then hold an invalid item
    until someone opens it and fills it in — this is the only way such a
    list grows without ever containing one.

    Carries the same concurrency token `item` does, despite targeting no
    position: two concurrent adds read the same list and, without a token,
    each would append to its own snapshot and call `save_list`, whose
    whole-column write (see its own docstring) means the second write simply
    erases the first append — both editors are still told "Élément ajouté.",
    and the list never grows past what a single add produced. The token
    turns the second, stale add into a refusal instead of a silent loss.
    """
    row, section_type, field = _list_context(pk, name)
    detail = (
        "impossible d'ajouter cet élément depuis cet écran."
        if request.method == "POST"
        else "impossible d'ouvrir l'ajout d'un élément depuis cet écran."
    )
    refusal = _refuse_if_unreadable(request, row, section_type, name, detail=detail)
    if refusal is not None:
        return refusal

    if _blocks_creation_without_uploads(field):
        messages.error(request, UPLOADS_BLOCK_REASON)
        return redirect("edition:section", pk=pk)

    values = list_values(row, section_type, name, field)
    values_digest = _digest(values)
    form_class = item_form_class(field)

    if request.method == "POST":
        refusal = _refuse_if_stale(request, row, values, digest=values_digest)
        if refusal is not None:
            return refusal
        form = form_class(request.POST, request.FILES)
        if form.is_valid():
            # A copy, not a mutation of `values`, for the same reason `item`
            # keeps one: `values_digest` must still describe what is
            # actually stored if this save is refused below (`max_num`, say).
            attempt = [*values, form.cleaned_data]
            try:
                save_list(row, section_type, name, attempt, field)
            except ValidationError as error:
                messages.error(request, error.messages[0])
            else:
                messages.success(request, "Élément ajouté.")
                return redirect("edition:section", pk=pk)
    else:
        form = form_class(initial=field.item_defaults())

    return render(
        request,
        "edition/item.html",
        {
            "row": row,
            "section_type": section_type,
            "field": field,
            "form": form,
            "token": values_digest,
            "creating": True,
        },
    )


def _boards(row, declared):
    """Everything the section screen shows about `row`'s lists.

    Called once, and only when the screen is actually about to render (a
    successful POST redirects away before ever reaching this: recomputing it
    then would be wasted work run on every save, for a page the request
    never shows).

    Returns `(boards, unreadable, overridden)`:

    - `boards`: `accueil.previews.section_lists`' own boards, minus any list
      whose stored override no longer validates (see `unreadable` below —
      showing that board would render the code's own fallback items as
      though they were the editor's), and with `can_add` narrowed by
      `_blocks_creation_without_uploads`: a declaration alone cannot know
      whether uploads are configured, only this view can. When that narrows
      `can_add`, `add_blocked_reason` carries the sentence to show where the
      "Ajouter" link would have been — a list at its own `max_num` already
      carries a different reason from `section_lists`, and is left as is.
    - `unreadable`: for each list whose override no longer validates, its
      *label* ("Témoignages", never the field's identifier — an editor never
      reads one) paired with the raw stored JSON, so an editor can copy out
      what is otherwise about to become the only way to recover it
      (`reset-field` drops it for good; the admin's own textarea is no help
      either, since it reads the same already-fallen-back content this
      screen would).
    - `overridden`: the labels of the section's *other*, scalar fields an
      editor has moved away from the code, in declaration order — for the
      generic "revenir au texte du code" list at the bottom. A list's own
      name is deliberately left out of it: resetting a whole hand-edited
      list is a different order of loss than resetting a one-line `kicker`,
      and the generic list has no way to say so — its own board carries
      that control instead, labelled for what it does.
    """
    list_names = [name for name, field in declared.Form.base_fields.items() if isinstance(field, ListField)]
    unreadable = {
        name: {
            "label": declared.Form.base_fields[name].label or name,
            "raw": json.dumps(row.content[name], ensure_ascii=False, indent=2),
        }
        for name in list_names
        if _override_is_unreadable(row, declared, name)
    }
    content = declared(row.content).content
    boards = []
    for board in section_lists(declared, content):
        if board["name"] in unreadable:
            continue
        field = declared.Form.base_fields[board["name"]]
        if board["can_add"] and _blocks_creation_without_uploads(field):
            board["can_add"] = False
            board["add_blocked_reason"] = UPLOADS_BLOCK_REASON
        board["customised"] = board["name"] in row.content
        boards.append(board)
    # Declaration order, not a `set`'s arbitrary one: an editor reading this
    # list twice should see the same order both times. A stored key the code
    # no longer declares at all (`stale_keys` on `SectionType`) has no label
    # to show instead, so it falls back to its own name, sorted after the
    # rest rather than interleaved arbitrarily.
    known = [name for name in declared.Form.base_fields if name in row.content and name not in list_names]
    unknown = sorted(name for name in row.content if name not in declared.Form.base_fields and name not in list_names)
    overridden = {name: declared.Form.base_fields[name].label or name for name in known}
    overridden.update({name: name for name in unknown})
    return boards, unreadable, overridden


@editor_view()
def section(request, pk):
    """Edit one section through the fields it declares.

    No per-section code: the form comes from the declaration, and only the
    values that differ from the code are stored.
    """
    row = get_object_or_404(Section, pk=pk, page__slug="accueil")
    declared = _declared(row.kind)
    if declared is None:
        messages.error(request, f"La section « {row.kind} » n'existe plus dans le code.")
        return redirect("edition:plan")

    form_class = section_form_class(declared, with_lists=False)
    if request.method == "POST":
        # `request.FILES` matters as soon as a section declares an
        # `Illustration`: without it the file input renders but the bytes never
        # reach the form, and the upload fails silently.
        form = form_class(request.POST, request.FILES, instance=row)
        if form.is_valid():
            form.save()
            messages.success(request, "Section enregistrée.")
            return redirect("edition:plan")
    else:
        form = form_class(instance=row)

    boards, unreadable, overridden = _boards(row, declared)
    return render(
        request,
        "edition/section.html",
        {
            "row": row,
            "name": declared.label,
            "anchor": declared.anchor,
            "form": form,
            # Which fields an editor has moved away from the code, so that a
            # wording changed in a pull request cannot go unnoticed.
            "overridden": overridden,
            "boards": boards,
            "unreadable_lists": unreadable,
        },
    )


def _field_label(row, name):
    """What an editor calls this field, falling back to its name only when the
    code no longer declares it and there is no label left to read."""
    section_type = _declared(row.kind)
    field = section_type.Form.base_fields.get(name) if section_type else None
    return getattr(field, "label", None) or name


@editor_view(post_only=True)
def reset_field(request, pk, name):
    """Drop one override, so the field follows the code again."""
    row = get_object_or_404(Section, pk=pk, page__slug="accueil")
    if row.content.pop(name, None) is not None:
        row.save(update_fields=["content"])
        # The label, never the identifier: identifiers are English precisely
        # because an editor never reads them.
        messages.success(request, f"« {_field_label(row, name)} » suit de nouveau le texte du code.")
    return redirect("edition:section", pk=pk)
