"""Featured support themes, mirrored layout."""

from django import forms

from accueil.sections.base import ListField, PlatformPath, registry
from accueil.sections.search import Card, SearchSection, Shortcut


@registry.register
class Services(SearchSection):
    key = "services"
    label = "Bloc de recherche — Services"
    position = 50
    anchor = "services"
    modifiers = "bloc-recherche bloc-recherche--inverse"
    cards_first = False
    badge_kind = "service"
    badge_label = "Service"
    stat_modifier = " carte-media__stat--service"

    class Form(forms.Form):
        kicker = forms.CharField(
            label="Surtitre",
            required=False,
            initial="Les services d'insertion",
        )
        title = forms.CharField(
            label="Titre",
            initial="Un accompagnement pour lever les freins à l’emploi.",
        )
        intro = forms.CharField(
            label="Introduction",
            required=False,
            widget=forms.Textarea,
            initial="Mobilité, logement, santé, formation… Sélectionnez une thématique pour trouver les services de votre territoire.",
        )
        cards = ListField(
            Card,
            label="Cartes en avant",
            min_num=1,
            max_num=3,
            initial=[
                {
                    "title": "La mobilité, un frein en moins",
                    "stat": "Permis, transport, véhicule",
                    "text": "Aide au permis, location solidaire, covoiturage : des solutions pour vos déplacements vers l'emploi.",
                    "icon": "ri-car-line",
                    "image": "accueil/img/service-mobilite.jpg",
                    "href": "/search/services/results?category=mobilite",
                },
                {
                    "title": "Le numérique s'ouvre à l'inclusion",
                    "stat": "60 parcours de formation",
                    "text": "Développement, support, data : de nouveaux métiers accessibles via des parcours adaptés.",
                    "icon": "ri-computer-line",
                    "image": "accueil/img/service-numerique.jpg",
                    "href": "/search/services/results?category=numerique",
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
                    "href": "/search/services/results?category=choisir-un-metier",
                    "icon": "ri-briefcase-line",
                    "label": "Choisir un métier",
                },
                {
                    "href": "/search/services/results?category=mobilite",
                    "icon": "ri-car-line",
                    "label": "Mobilité",
                },
                {
                    "href": "/search/services/results?category=famille",
                    "icon": "ri-group-line",
                    "label": "Famille",
                },
                {
                    "href": "/search/services/results?category=creer-une-entreprise",
                    "icon": "ri-rocket-line",
                    "label": "Créer une entreprise",
                },
                {
                    "href": "/search/services/results?category=preparer-sa-candidature",
                    "icon": "ri-file-list-3-line",
                    "label": "Préparer sa candidature",
                },
                {
                    "href": "/search/services/results?category=se-former",
                    "icon": "ri-graduation-cap-line",
                    "label": "Se former",
                },
                {
                    "href": "/search/services/results?category=difficultes-financieres",
                    "icon": "ri-money-euro-circle-line",
                    "label": "Difficultés financières",
                },
                {
                    "href": "/search/services/results?category=sante",
                    "icon": "ri-heart-pulse-line",
                    "label": "Santé",
                },
            ],
        )
        see_all_label = forms.CharField(label="Lien « voir tout »", initial="Voir toutes les thématiques")
        see_all_href = PlatformPath(label="Cible du lien", initial="/search/services/results")
