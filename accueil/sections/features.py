"""What the platform does, as a numbered timeline."""

from django import forms

from accueil.sections.base import ListField, SectionType, registry


class Step(forms.Form):
    icon = forms.CharField(label="Icône")
    title = forms.CharField(label="Titre")
    text = forms.CharField(label="Texte", required=False, widget=forms.Textarea)


@registry.register
class Features(SectionType):
    key = "features"
    label = "Frise de parcours"
    position = 20
    template = "accueil/sections/features.html"
    anchor = "fonctionnalites"
    modifiers = "section--bleu"

    class Form(forms.Form):
        kicker = forms.CharField(label="Surtitre", required=False, initial="L'outil pour travailler ensemble")
        title = forms.CharField(label="Titre", initial="Tout votre quotidien professionnel, au même endroit.")
        intro = forms.CharField(
            label="Introduction",
            required=False,
            widget=forms.Textarea,
            initial="La plateforme qui réunit les professionnels de l'inclusion et leurs bénéficiaires.",
        )
        steps = ListField(
            Step,
            label="Étapes",
            min_num=1,
            max_num=6,
            initial=[
                {
                    "icon": "ri-briefcase-line",
                    "title": "Recruter et candidater",
                    "text": "Publier vos postes, recevoir les candidatures, obtenir les PASS IAE.",
                },
                {
                    "icon": "ri-user-shared-line",
                    "title": "Orienter des candidats",
                    "text": "Adresser vos bénéficiaires et suivre leurs candidatures.",
                },
                {
                    "icon": "ri-compass-3-line",
                    "title": "Trouver des solutions",
                    "text": "Repérer les services d'accompagnement de votre territoire.",
                },
                {
                    "icon": "ri-line-chart-line",
                    "title": "Piloter votre activité",
                    "text": "Suivre vos indicateurs et tableaux de bord territoriaux.",
                },
                {
                    "icon": "ri-route-line",
                    "title": "Accompagner les parcours",
                    "text": "Centraliser le suivi : récap, immersions, historique.",
                },
            ],
        )
