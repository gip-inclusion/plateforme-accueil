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

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_deny
from django.views.decorators.csp import csp_override
from django.views.decorators.http import require_POST

from accueil.forms import section_form_class
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


def list_values(row, section_type, name):
    """The list as it renders: the override if there is one, else the code.

    Known limitation, deliberately left unaddressed here: `SectionType.__init__`
    swallows a per-field `ValidationError` and falls back to the code default
    when an override no longer validates (a rule tightened after the override
    was written, say). That is the right behaviour for the public page, but on
    an editing screen it means an editor is shown the code's content in place
    of their own unreadable override, with nothing to say so — and their next,
    otherwise unrelated save silently discards it for good. Tasks 9–11 need to
    surface this, not this helper.
    """
    _list_field(section_type, name)  # 404 on a bad name, before touching row.content
    row_content = row.content if isinstance(row.content, dict) else {}
    return copy.deepcopy(section_type(row_content).content[name])


def save_list(row, section_type, name, values):
    """Validate a list whole, then write it back. Returns the cleaned list.

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
    field = _list_field(section_type, name)
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
