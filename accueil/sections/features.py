"""What the platform does, as a numbered timeline."""

from django import forms

from accueil.sections.base import SectionType, registry


@registry.register
class Features(SectionType):
    key = "features"
    label = "Frise de parcours"
    position = 20
    template = "accueil/sections/features.html"

    class Form(forms.Form):
        kicker = forms.CharField(
            label="Surtitre",
            required=False,
            initial="L'outil pour travailler ensemble",
        )
        title = forms.CharField(
            label="Titre",
            initial="Tout votre quotidien professionnel, au même endroit.",
        )
        intro = forms.CharField(
            label="Introduction",
            required=False,
            widget=forms.Textarea,
            initial="La plateforme qui réunit les professionnels de l'inclusion et leurs bénéficiaires.",
        )
