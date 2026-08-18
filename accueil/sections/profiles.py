"""Tabbed journeys, one per kind of user."""

from django import forms

from accueil.sections.base import ListField, Reference, SectionType, registry


class Step(forms.Form):
    title = forms.CharField(label="Titre")
    detail = forms.CharField(label="Détail", required=False)


class Profile(forms.Form):
    slug = Reference(label="Identifiant", help_text="Relie l'onglet à son panneau.")
    tab_label = forms.CharField(label="Onglet")
    icon = forms.CharField(label="Icône")
    title = forms.CharField(label="Titre")
    chapo = forms.CharField(label="Chapô", required=False, widget=forms.Textarea)
    cta_label = forms.CharField(label="Bouton")
    cta_href = forms.URLField(label="Cible du bouton")
    steps = ListField(Step, label="Étapes", min_num=1, max_num=6)


@registry.register
class Profiles(SectionType):
    key = "profiles"
    label = "Parcours par profil"
    position = 80
    template = "accueil/sections/profiles.html"
    anchor = "pour-qui"
    modifiers = "section--lisere profils"

    class Form(forms.Form):
        kicker = forms.CharField(label="Surtitre", required=False, initial="Pour qui ?")
        title = forms.CharField(label="Titre", initial="Des services utiles à tous les pros du Réseau pour l'emploi.")
        profiles = ListField(
            Profile,
            label="Profils",
            min_num=1,
            max_num=6,
            unique="slug",
            initial=[
                {
                    "slug": "prescripteur",
                    "icon": "ri-home-smile-2-line",
                    "tab_label": "Accompagnateur",
                    "title": "Orientez vos candidats vers l'emploi durable",
                    "chapo": "Adressez vos bénéficiaires aux employeurs inclusifs de votre territoire et suivez chaque parcours depuis votre espace.",
                    "cta_href": "https://emplois.inclusion.beta.gouv.fr/signup/professional/user",
                    "cta_label": "S'inscrire",
                    "steps": [
                        {
                            "title": "Créer votre compte prescripteur",
                            "detail": "Avec ProConnect, en quelques minutes.",
                        },
                        {
                            "title": "Rechercher un employeur ou une solution",
                            "detail": "Emplois inclusifs et services d'accompagnement, au même endroit.",
                        },
                        {
                            "title": "Adresser la candidature",
                            "detail": "Le dossier de votre bénéficiaire suit, sans ressaisie.",
                        },
                        {
                            "title": "Suivre le parcours",
                            "detail": "Candidatures, PASS IAE et récap de parcours dans votre espace.",
                        },
                    ],
                },
                {
                    "slug": "employeur",
                    "icon": "ri-community-line",
                    "tab_label": "Employeur inclusif",
                    "title": "Recrutez et gérez vos PASS IAE en ligne",
                    "chapo": "SIAE, GEIQ, EA ou facilitateur : publiez vos postes et gérez vos obligations déclaratives sans changer d'outil.",
                    "cta_href": "https://emplois.inclusion.beta.gouv.fr/signup/professional/user",
                    "cta_label": "S'inscrire",
                    "steps": [
                        {
                            "title": "Créer le compte de votre structure",
                            "detail": "Et inviter vos collaborateurs à vous rejoindre.",
                        },
                        {
                            "title": "Publier vos fiches de poste",
                            "detail": "Visibles des candidats et des prescripteurs habilités.",
                        },
                        {
                            "title": "Recevoir et traiter les candidatures",
                            "detail": "Trier, répondre et planifier vos entretiens.",
                        },
                        {
                            "title": "Obtenir le PASS IAE dès l'embauche",
                            "detail": "Et déclarer votre activité pour vos financements.",
                        },
                    ],
                },
                {
                    "slug": "institution",
                    "icon": "ri-government-line",
                    "tab_label": "Institution partenaire",
                    "title": "Pilotez l'insertion sur votre territoire",
                    "chapo": "DDETS, conseils départementaux, France Travail : disposez d'une vision consolidée de l'offre et des parcours d'insertion.",
                    "cta_href": "https://emplois.inclusion.beta.gouv.fr/signup/professional/user",
                    "cta_label": "S'inscrire",
                    "steps": [
                        {
                            "title": "Créer votre compte institution",
                            "detail": "Avec votre adresse professionnelle, via ProConnect.",
                        },
                        {
                            "title": "Accéder aux tableaux de bord",
                            "detail": "Indicateurs territoriaux actualisés en continu.",
                        },
                        {
                            "title": "Suivre le déploiement des dispositifs",
                            "detail": "IAE, immersions, accompagnement : une vision d'ensemble.",
                        },
                        {
                            "title": "Exploiter les données ouvertes",
                            "detail": "Le socle data·inclusion, documenté et réutilisable.",
                        },
                    ],
                },
                {
                    "slug": "candidat",
                    "icon": "ri-user-line",
                    "tab_label": "Candidat",
                    "title": "Trouvez un emploi près de chez vous",
                    "chapo": "Recherchez un emploi inclusif, postulez et suivez vos candidatures — seul ou avec votre accompagnateur.",
                    "cta_href": "https://emplois.inclusion.beta.gouv.fr/signup/job_seeker/start",
                    "cta_label": "S'inscrire",
                    "steps": [
                        {
                            "title": "Créer votre compte",
                            "detail": "En quelques minutes, sans justificatif.",
                        },
                        {
                            "title": "Rechercher un emploi inclusif",
                            "detail": "Autour de chez vous, selon vos critères.",
                        },
                        {
                            "title": "Postuler ou être accompagné",
                            "detail": "Seul ou avec l'aide d'un prescripteur.",
                        },
                        {
                            "title": "Suivre vos candidatures",
                            "detail": "Et retrouver votre récap de parcours à tout moment.",
                        },
                    ],
                },
            ],
        )
