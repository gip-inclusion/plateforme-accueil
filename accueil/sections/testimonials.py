"""Quotes from users of the platform."""

from django import forms

from accueil.sections.base import SectionType, registry


@registry.register
class Testimonials(SectionType):
    key = "testimonials"
    label = "Témoignages"
    position = 70
    template = "accueil/sections/testimonials.html"

    class Form(forms.Form):
        kicker = forms.CharField(
            label="Surtitre",
            required=False,
            initial="Témoignages",
        )
        title = forms.CharField(
            label="Titre",
            initial="Ils utilisent La plateforme de l'inclusion.",
        )
