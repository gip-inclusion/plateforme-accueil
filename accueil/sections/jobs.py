"""Featured job sectors: media cards plus shortcut pills."""

from django import forms

from accueil.sections.base import ListField, PlatformPath, registry
from accueil.sections.search import Card, SearchSection, Shortcut


@registry.register
class Jobs(SearchSection):
    key = "jobs"
    label = "Bloc de recherche — Emplois"
    position = 40
    anchor = "emplois"
    modifiers = "section--grisee bloc-recherche"
    cards_first = True
    badge_kind = "emploi"
    badge_label = "Emploi"
    stat_modifier = ""

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
        cards = ListField(
            Card,
            label="Cartes en avant",
            min_num=1,
            max_num=3,
            initial=[
                {
                    "title": "Les espaces verts embauchent toute l'année",
                    "stat": "+ de 3 700 embauches ce trimestre",
                    "text": "Entretien, jardinage, espaces naturels : les structures d'insertion forment et embauchent toute l'année.",
                    "icon": "ri-plant-line",
                    "image": "accueil/img/emploi-espacesverts.jpg",
                    "image_credit": "Biekir Litovchenko / Pexels, licence Pexels",
                    "href": "/search/job-descriptions/results?domains=A",
                },
                {
                    "title": "Le service à la personne recrute et forme",
                    "stat": "+ de 1 200 recrutements ce trimestre",
                    "text": "Aide à domicile, entretien, garde : des postes accessibles et un accompagnement à la prise de fonction.",
                    "icon": "ri-group-line",
                    "image": "accueil/img/emploi-aidedomicile.jpg",
                    "image_credit": "Jsme MILA / Pexels, licence Pexels",
                    "href": "/search/job-descriptions/results?domains=K",
                },
            ],
        )
        shortcuts = ListField(
            Shortcut,
            label="Raccourcis",
            min_num=1,
            max_num=12,
            initial=[
                {
                    "href": "/search/job-descriptions/results?domains=H",
                    "icon": "ri-building-2-line",
                    "label": "Industrie",
                },
                {
                    "href": "/search/job-descriptions/results?domains=N",
                    "icon": "ri-truck-line",
                    "label": "Transport et logistique",
                },
                {
                    "href": "/search/job-descriptions/results?domains=A",
                    "icon": "ri-plant-line",
                    "label": "Agriculture et pêche",
                },
                {
                    "href": "/search/job-descriptions/results?domains=I",
                    "icon": "ri-tools-line",
                    "label": "Installation et maintenance",
                },
                {
                    "href": "/search/job-descriptions/results?domains=L",
                    "icon": "ri-mic-line",
                    "label": "Spectacle",
                },
                {
                    "href": "/search/job-descriptions/results?domains=C",
                    "icon": "ri-bank-line",
                    "label": "Banque, assurance, immobilier",
                },
                {
                    "href": "/search/job-descriptions/results?domains=B",
                    "icon": "ri-brush-line",
                    "label": "Art et façonnage d'ouvrages d'art",
                },
            ],
        )
        see_all_label = forms.CharField(label="Lien « voir tout »", initial="Voir tous les secteurs")
        see_all_href = PlatformPath(label="Cible du lien", initial="/search/job-descriptions/results")
