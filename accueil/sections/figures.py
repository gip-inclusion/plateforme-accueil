"""Key figures band, fed daily by the open-data dashboard."""

from django import forms

from accueil.sections.base import SectionType, registry


@registry.register
class Figures(SectionType):
    key = "figures"
    label = "Chiffres clés"
    position = 30
    template = "accueil/sections/figures.html"

    class Form(forms.Form):
        kicker = forms.CharField(
            label="Surtitre",
            required=False,
            initial="Toutes les ressources, tous les partenaires",
        )
        title = forms.CharField(
            label="Titre",
            initial="Ça se passe sur La plateforme de l'inclusion.",
        )
