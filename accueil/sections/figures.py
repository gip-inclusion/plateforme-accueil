"""Key figures band, fed daily by the open-data dashboard."""

from django import forms

from accueil import key_figures
from accueil.sections.base import Illustration, ListField, Reference, SectionType, registry


class Indicator(forms.Form):
    key = Reference(label="Identifiant dans le flux")
    label = forms.CharField(label="Libellé")
    image = Illustration(
        label="Pictogramme",
        # .stat__illu is height-driven (height: 4rem = 64px at the >=48rem
        # breakpoint), rendering ~91px wide at this ratio; twice is ~182,
        # rounded up. No `initial`: each of the three real indicators has its
        # own pictogram, so guessing one for a fourth would be wrong more
        # often than not — see Card.image, which makes the same call.
        max_width=190,
        ratio=(122, 86),
    )
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
                    "label": "offres d'emploi ouvertes",
                    "image": "accueil/img/stat-emploi.webp",
                    "fallback": 11553,
                },
                {
                    "key": "services_di",
                    "label": "services d'insertion référencés",
                    "image": "accueil/img/stat-insertion.webp",
                    "fallback": 198430,
                },
                {
                    "key": "prescripteurs_actifs",
                    "label": "structures d'accompagnement actives",
                    "image": "accueil/img/stat-prescripteurs.webp",
                    "fallback": 5310,
                },
            ],
        )
