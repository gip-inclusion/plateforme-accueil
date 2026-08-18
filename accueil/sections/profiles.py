"""Tabbed journeys, one per kind of user."""

from accueil.sections.base import SectionType, registry


@registry.register
class Profiles(SectionType):
    key = "profiles"
    label = "Parcours par profil"
    position = 80
    template = "accueil/sections/profiles.html"
