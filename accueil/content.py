"""Assembling the page: code defaults, plus whatever an editor changed.

The defaults declared in `accueil/sections/` are the source of truth for
content. This module layers the database on top, and is written so that the
page renders no matter what: no database configured, database unreachable,
tables not migrated yet — all fall back to the defaults.
"""

from django.conf import settings
from django.core.cache import cache

from accueil.sections import registry


OVERRIDES_CACHE_KEY = "cms:overrides"
# Short-lived pointer rather than explicit invalidation: several serverless
# instances cannot invalidate each other's local cache, so an edit becomes
# visible everywhere within this delay instead.
OVERRIDES_CACHE_TTL = 30  # seconds


def page_sections(slug="accueil"):
    """Every visible section of the page, in render order."""
    overrides = _overrides(slug)
    sections = []
    for section_type in registry.types():
        override = overrides.get(section_type.key)
        if override is None:
            sections.append(section_type())  # never edited: pure code defaults
            continue
        if not override["active"]:
            continue
        section = section_type(override["content"])
        section.position = override["position"]
        sections.append(section)
    return sorted(sections, key=lambda section: section.position)


def _overrides(slug):
    if not settings.DATABASE_CONFIGURED:
        return {}

    overrides = cache.get(OVERRIDES_CACHE_KEY)
    if overrides is not None:
        return overrides

    from accueil.models import Section

    try:
        overrides = {
            section.kind: {
                "active": section.active,
                "position": section.position,
                "content": section.content,
            }
            for section in Section.objects.filter(page__slug=slug)
        }
    except Exception:
        # Unreachable database, missing table, blocked query in tests: the page
        # matters more than the overrides. Not cached, so it self-heals.
        return {}

    cache.set(OVERRIDES_CACHE_KEY, overrides, OVERRIDES_CACHE_TTL)
    return overrides
