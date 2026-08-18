"""Key figures band, fed daily by the open-data dashboard."""

from accueil.sections.base import SectionType, registry


@registry.register
class Figures(SectionType):
    key = "figures"
    label = "Chiffres clés"
    position = 30
    template = "accueil/sections/figures.html"
