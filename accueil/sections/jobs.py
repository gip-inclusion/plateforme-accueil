"""Featured job sectors: media cards plus shortcut pills."""

from django import forms

from accueil.sections.base import SectionType, registry


@registry.register
class Jobs(SectionType):
    key = "jobs"
    label = "Bloc de recherche — Emplois"
    position = 40
    template = "accueil/sections/jobs.html"

    class Form(forms.Form):
        kicker = forms.CharField(
            label="Surtitre",
            required=False,
            initial="L'inclusion par l'emploi",
        )
        title = forms.CharField(
            label="Titre",
            initial="Des postes en entreprises et structures d'insertion, partout en France.",
        )
        intro = forms.CharField(
            label="Introduction",
            required=False,
            widget=forms.Textarea,
            initial="Les employeurs inclusifs embauchent en priorité les personnes éloignées de l'emploi. Choisissez un secteur pour découvrir les offres près de chez vous.",
        )
