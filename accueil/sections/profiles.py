"""Tabbed journeys, one per kind of user."""

from django import forms

from accueil.sections.base import SectionType, registry


@registry.register
class Profiles(SectionType):
    key = "profiles"
    label = "Parcours par profil"
    position = 80
    template = "accueil/sections/profiles.html"

    class Form(forms.Form):
        kicker = forms.CharField(
            label="Surtitre",
            required=False,
            initial="Pour qui ?",
        )
        title = forms.CharField(
            label="Titre",
            initial="Des services utiles à tous les pros du Réseau pour l'emploi.",
        )
