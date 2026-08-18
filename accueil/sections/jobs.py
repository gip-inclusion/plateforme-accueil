"""Featured job sectors: media cards plus shortcut pills."""

from accueil.sections.base import SectionType, registry


@registry.register
class Jobs(SectionType):
    key = "jobs"
    label = "Bloc de recherche — Emplois"
    position = 40
    template = "accueil/sections/jobs.html"
