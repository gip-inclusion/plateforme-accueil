"""Key figures band, fed daily by the open-data dashboard."""

from django import forms

from accueil import key_figures
from accueil.sections.base import ListField, Reference, SectionType, registry


class Indicator(forms.Form):
    key = Reference(label="Identifiant dans le flux")
    label = forms.CharField(label="Libellé")
    image = forms.CharField(label="Image", help_text="Chemin sous accueil/static/")
    fallback = forms.IntegerField(
        label="Valeur de repli",
        help_text="Affichée si le flux est injoignable.",
    )


@registry.register
class Figures(SectionType):
    key = "figures"
    label = "Chiffres clés"
    position = 30
    template = "accueil/sections/figures.html"

    @property
    def values(self):
        """The declared indicators, each paired with its current value."""
        return key_figures.resolve(self.content["indicators"])

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
        indicators = ListField(
            Indicator,
            label="Indicateurs",
            min_num=1,
            max_num=4,
            initial=[
                {
                    "key": "offres_ouvertes",
                    "label": "offres d'emploi inclusif",
                    "image": "accueil/img/stat-emploi.webp",
                    "fallback": 11553,
                },
                {
                    "key": "services_di",
                    "label": "services d'insertion",
                    "image": "accueil/img/stat-insertion.webp",
                    "fallback": 198430,
                },
                {
                    "key": "prescripteurs_actifs",
                    "label": "prescripteurs habilités",
                    "image": "accueil/img/stat-prescripteurs.webp",
                    "fallback": 5310,
                },
            ],
        )
