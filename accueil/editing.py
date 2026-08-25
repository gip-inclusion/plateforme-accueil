"""The editing UI: a plan of the page, not a list of tables.

An editor thinks « the figures band sits too high », never « table Section,
column position ». So the entry point is the page in miniature: reorder, show
or hide, then drill into a section.

Never embeddable, and never public: every view here denies framing outright and
requires an account that Authentik put in the editing group. Alongside the
views, this module also holds `list_values`/`save_list`, the request-free
storage helpers a list's own editing screen (Tasks 9–11) reads and writes
through — they know nothing about HTTP and raise `Http404` rather than
redirect, so a view wraps them, not the other way round.
"""

import copy
import hashlib
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
from accueil.models import Page, Section
from accueil.sections import ListField, registry


def may_publish(user):
    return user.is_superuser or user.groups.filter(name=settings.OIDC_PUBLISHER_GROUP).exists()


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
    """One line describing the section by its content, not by its type."""
    content = section_type(section.content).content
    title = content.get("title") or content.get("kicker") or ""
    counts = [f"{len(value)} {name}" for name, value in content.items() if isinstance(value, list) and value]
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
            "oidc_enabled": settings.OIDC_ENABLED,
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


def _list_field(section_type, name):
    """The declared `ListField` for `name`, or a 404.

    A missing or mistyped `name` only ever reaches here from a URL segment
    (Tasks 9–11), so it is the caller's routing that is wrong, not the data —
    the same lens `get_object_or_404` applies to a bad primary key. Without
    this, a name that exists but names some other kind of field (`"title"`)
    would still reach `Field.clean`, which happily stringifies a list into
    `"['a', 'b']"` and lets it through: nothing downstream would catch that
    before it lands in the database.
    """
    field = section_type.Form.base_fields.get(name)
    if not isinstance(field, ListField):
        raise Http404(f"« {name} » n'est pas une liste déclarée sur « {section_type.key} ».")
    return field


def list_values(row, section_type, name, field=None):
    """The list as it renders: the override if there is one, else the code.

    `field` lets a caller that already resolved it through `_list_context`
    pass it straight in, rather than have `_list_field` look it up again.

    Known limitation, deliberately left unaddressed here: `SectionType.__init__`
    swallows a per-field `ValidationError` and falls back to the code default
    when an override no longer validates (a rule tightened after the override
    was written, say). That is the right behaviour for the public page, but on
    an editing screen it means an editor is shown the code's content in place
    of their own unreadable override, with nothing to say so. `_apply` guards
    against this with `_override_is_unreadable` before it ever calls this
    function to mutate anything; a bare read through this helper (the section
    screen's own display, say) still shows the code's content silently, which
    remains a Task 10/11 concern, not this one.
    """
    field = field or _list_field(section_type, name)  # 404 on a bad name, before touching row.content
    row_content = row.content if isinstance(row.content, dict) else {}
    return copy.deepcopy(section_type(row_content).content[name])


def save_list(row, section_type, name, values, field=None):
    """Validate a list whole, then write it back. Returns the cleaned list.

    `field` lets a caller that already resolved it through `_list_context`
    pass it straight in, rather than have `_list_field` look it up again.

    Validating the whole list on every write — not just the touched item — is
    what makes `min_num`, `max_num` and `unique` hold: removing the last
    indicator must be refused, not accepted.

    Returns `cleaned`, not `values`: cleaning can change the shape (an
    injected `..._credit` key, a coerced integer), so a caller that chains a
    second operation must carry on from what was actually stored, not from
    what it originally passed in.

    Last-write-wins: this writes the whole `content` column, so a concurrent
    edit — of this list or of any other field on the same section — made
    between this row being loaded and this save is silently overwritten. That
    was already true of the section form this replaces; the repeater turns
    every add, duplicate, move and delete into its own full-column write,
    which multiplies the exposure but does not change its nature. Acceptable
    for a small editorial team working one section at a time; revisit if that
    stops being true.
    """
    field = field or _list_field(section_type, name)
    if not isinstance(row.content, dict):
        row.content = {}
    cleaned = field.clean(values)
    if cleaned == field.clean(copy.deepcopy(field.initial)):
        # Back to the code's own values: the override no longer has a reason
        # to exist, and the section follows pull requests again.
        row.content.pop(name, None)
    else:
        row.content[name] = cleaned
    row.save(update_fields=["content"])
    return cleaned


def _override_is_unreadable(row, section_type, name):
    """True when `row.content` holds an override for `name` that no longer
    validates, and `SectionType.__init__` has silently fallen back to the
    code default for it (see the limitation documented on `list_values`).

    Acting on such a list would be destructive: `list_values` would hand
    back the code's own items, an item operation would mutate those, and
    `save_list` would write them back as if they were the editor's, erasing
    whatever they had actually written with no message and nothing left to
    recover. `_apply` calls this first and refuses the operation instead.
    """
    row_content = row.content if isinstance(row.content, dict) else {}
    if name not in row_content:
        return False
    try:
        section_type.clean_value(name, row_content[name])
    except ValidationError:
        return True
    return False


def _digest(values):
    """A short fingerprint of a list's cleaned content.

    Carried on the POST as an optimistic-concurrency token: the screen that
    renders the list (Task 10/11) embeds the digest of the list as it was
    read, and `_apply` refuses the operation rather than apply it if the
    list has changed underneath since — the only signal available for a
    list whose items were deliberately left without a stored identity.
    """
    payload = json.dumps(values, sort_keys=True, default=str).encode()
    return hashlib.sha256(payload).hexdigest()[:16]


def _refuse_if_unreadable(request, pk, row, section_type, name):
    """Redirect to the section, with a flash message, if `name`'s stored
    override no longer validates — the same refusal `_apply` applies before
    a duplicate, move or delete, and needed here for the same reason: acting
    on `list_values`' silent fallback to the code default would replace an
    editor's unreadable-but-real override with content built from the code,
    with nothing to say so.
    """
    if not _override_is_unreadable(row, section_type, name):
        return None
    messages.error(
        request,
        "Cette liste contient une modification qui n'est plus reconnue par le code : "
        "impossible d'agir dessus depuis cet écran. Rien n'a été modifié.",
    )
    return redirect("edition:section", pk=pk)


def _apply(request, pk, name, change):
    """Apply one operation to a list, and say so — success or refusal alike.

    Two guards run before `change` ever sees the list, in addition to the
    whole-list validation `save_list` already does:

    - an override that no longer validates is left untouched rather than
      silently replaced by the code defaults, see `_override_is_unreadable`;
    - the POST must carry a `token` matching `_digest` of the list as read
      here, or the operation is refused as stale. The token is required, not
      optional: were it optional, a template that forgot to send it (Task 10,
      11) would simply never trigger the guard, rather than fail loudly with
      buttons that do not work. This is deliberately the same guard for a
      missing token and a mismatched one — both mean this POST cannot be
      trusted to describe the list as it now stands.
    """
    row, section_type, field = _list_context(pk, name)
    refusal = _refuse_if_unreadable(request, pk, row, section_type, name)
    if refusal is not None:
        return refusal

    values = list_values(row, section_type, name, field)
    if request.POST.get("token") != _digest(values):
        messages.error(
            request,
            "Cette liste a changé depuis l'affichage de la page. Rien n'a été modifié : rechargez et réessayez.",
        )
        return redirect("edition:section", pk=pk)

    try:
        change(values)
        save_list(row, section_type, name, values, field)
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return redirect("edition:section", pk=pk)

    messages.success(request, "Élément mis à jour.")
    return redirect("edition:section", pk=pk)


@editor_view(post_only=True)
def item_duplicate(request, pk, name, index):
    # Structurally unusable on a list declaring `unique` (`profiles`, on
    # `slug`): every duplicate collides with the item it copies and is
    # refused by `save_list`'s whole-list validation, cleanly and with
    # nothing written. That list has no way to grow until Task 10 adds a
    # creation form — a known state, not a bug to fix here.
    def change(values):
        _check_index(values, index)
        values.insert(index + 1, copy.deepcopy(values[index]))

    return _apply(request, pk, name, change)


@editor_view(post_only=True)
def item_delete(request, pk, name, index):
    def change(values):
        _check_index(values, index)
        values.pop(index)

    return _apply(request, pk, name, change)


@editor_view(post_only=True)
def item_move(request, pk, name, index):
    return _apply(request, pk, name, _swap(index, request.POST.get("direction")))


def _swap(index, direction):
    """Build a move, as a plain list mutation — no `request` in here.

    An unrecognised or absent `direction` is a no-op, not a downward move:
    only "up" and "down" carry meaning. Landing past either end of the list
    is a no-op too, and that is only correct for a screen that withholds the
    button there in the first place — the contract Task 10/11's template
    must honour.
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


@editor_view()
def item(request, pk, name, index):
    """Edit one item of a list through the fields its item form declares.

    No concurrency token, unlike `_apply`'s operations: those act blindly on
    a bare index, so a stale click can silently land on the wrong item. Here
    the editor reviews and resubmits the item's own fields, and a concurrent
    change to the rest of the list — an item removed elsewhere, say — is the
    same last-write-wins exposure `save_list` already documents and accepts
    for the section form this replaces; adding a token would only guard the
    read of `values[index]` used to seed the GET form, not the write, so it
    was left out rather than added as a guard against a race it cannot
    actually close.
    """
    row, section_type, field = _list_context(pk, name)
    refusal = _refuse_if_unreadable(request, pk, row, section_type, name)
    if refusal is not None:
        return refusal

    values = list_values(row, section_type, name, field)
    _check_index(values, index)

    form_class = item_form_class(field)
    if request.method == "POST":
        form = form_class(request.POST, request.FILES)
        if form.is_valid():
            values[index] = form.cleaned_data
            try:
                save_list(row, section_type, name, values, field)
            except ValidationError as error:
                messages.error(request, error.messages[0])
                return redirect("edition:section", pk=pk)
            messages.success(request, "Élément mis à jour.")
            return redirect("edition:section", pk=pk)
    else:
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
    """
    row, section_type, field = _list_context(pk, name)
    refusal = _refuse_if_unreadable(request, pk, row, section_type, name)
    if refusal is not None:
        return refusal

    form_class = item_form_class(field)
    if request.method == "POST":
        form = form_class(request.POST, request.FILES)
        if form.is_valid():
            values = list_values(row, section_type, name, field)
            values.append(form.cleaned_data)
            try:
                save_list(row, section_type, name, values, field)
            except ValidationError as error:
                messages.error(request, error.messages[0])
                return redirect("edition:section", pk=pk)
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
            "creating": True,
        },
    )


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

    form_class = section_form_class(declared)
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

    overridden = set(row.content)
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
        },
    )


@editor_view(post_only=True)
def reset_field(request, pk, name):
    """Drop one override, so the field follows the code again."""
    row = get_object_or_404(Section, pk=pk, page__slug="accueil")
    if row.content.pop(name, None) is not None:
        row.save(update_fields=["content"])
        messages.success(request, f"« {name} » suit de nouveau le texte du code.")
    return redirect("edition:section", pk=pk)
