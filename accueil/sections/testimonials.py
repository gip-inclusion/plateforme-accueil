"""Quotes from users of the platform."""

from django import forms

from accueil.sections.base import Illustration, ListField, SectionType, registry


class Quote(forms.Form):
    quote = forms.CharField(label="Citation", widget=forms.Textarea)
    name = forms.CharField(label="Nom")
    role = forms.CharField(label="Fonction", required=False)


@registry.register
class Testimonials(SectionType):
    key = "testimonials"
    label = "Témoignages"
    position = 70
    template = "accueil/sections/testimonials.html"
    anchor = "temoignages"
    modifiers = "temoignages"

    class Form(forms.Form):
        kicker = forms.CharField(label="Surtitre", required=False, initial="Témoignages")
        title = forms.CharField(label="Titre", initial="Ils utilisent La plateforme de l'inclusion.")
        quotes = ListField(
            Quote,
            label="Témoignages",
            min_num=1,
            max_num=4,
            initial=[
                {
                    "quote": "Un seul compte pour tout mon quotidien : orienter, suivre, échanger. Je gagne un temps précieux à chaque accompagnement.",
                    "name": "Nadia B.",
                    "role": "Conseillère en insertion, Mission locale, Lille",
                },
                {
                    "quote": "Nous délivrons les PASS IAE en ligne et suivons nos indicateurs au même endroit. L'outil s'est effacé derrière le métier.",
                    "name": "Marc D.",
                    "role": "Directeur de SIAE, Nantes",
                },
            ],
        )
        illustration = Illustration(
            label="Illustration",
            # .temoignages__illu caps at max-width: 20rem (320px); twice, for
            # dense screens.
            max_width=640,
            ratio=(56, 34),
            initial="accueil/img/temoignages-illustration.webp",
        )
