"""Featured support themes, mirrored layout."""

from accueil.sections.base import SectionType, registry


@registry.register
class Services(SectionType):
    key = "services"
    label = "Bloc de recherche — Services"
    position = 50
    template = "accueil/sections/services.html"
