"""Call to action towards the prescriber search."""

from accueil.sections.base import SectionType, registry


@registry.register
class Advisors(SectionType):
    key = "advisors"
    label = "Accompagnateurs"
    position = 60
    template = "accueil/sections/advisors.html"
