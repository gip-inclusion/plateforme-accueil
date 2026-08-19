"""The editing UI: a plan of the page, not a list of tables.

An editor thinks « the figures band sits too high », never « table Section,
column position ». So the entry point is the page in miniature: reorder, show
or hide, then drill into a section.

Never embeddable, and never public: every view here denies framing outright and
requires an account that Authentik put in the editing group.
"""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_deny
from django.views.decorators.csp import csp_override
from django.views.decorators.http import require_POST

from accueil.forms import section_form_class
from accueil.models import Page, Section
from accueil.sections import registry


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
        form = form_class(request.POST, instance=row)
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
