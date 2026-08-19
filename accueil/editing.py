"""The editing UI: a plan of the page, not a list of tables.

An editor thinks « the figures band sits too high », never « table Section,
column position ». So the entry point is the page in miniature: reorder, show
or hide, then drill into a section.

Never embeddable, and never public: every view here denies framing outright and
requires an account that Authentik put in the editing group.
"""

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_deny
from django.views.decorators.csp import csp_override
from django.views.decorators.http import require_POST

from accueil.auth import may_publish
from accueil.models import Page, Section
from accueil.sections import registry


# The public page is meant to be framed; this one must not be. Both are set
# explicitly so that no future change to the site-wide CSP can open it up.
def editor_view(view):
    for decorator in (
        staff_member_required,
        xframe_options_deny,
        csp_override({"frame-ancestors": ["'none'"]}),
    ):
        view = decorator(view)
    return view


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
                "url": reverse("admin:accueil_section_change", args=[section.pk]),
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


@editor_view
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


@require_POST
@editor_view
def move(request, pk):
    """Swap a section with its neighbour. A form post, so it works without JS."""
    section = Section.objects.get(pk=pk)
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


@require_POST
@editor_view
def toggle(request, pk):
    section = Section.objects.get(pk=pk)
    section.active = not section.active
    section.save(update_fields=["active"])
    return redirect("edition:plan")
