"""What the platform does, as a numbered timeline."""

from accueil.sections.base import SectionType, registry


@registry.register
class Features(SectionType):
    key = "features"
    label = "Frise de parcours"
    position = 20
    template = "accueil/sections/features.html"
