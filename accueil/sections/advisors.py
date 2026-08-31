"""Call to action towards the prescriber search."""

from django import forms

from accueil.sections.base import Icon, ListField, PlatformPath, SectionType, registry


class Tag(forms.Form):
    icon = Icon(label="Icône")
    label = forms.CharField(label="Libellé")


@registry.register
class Advisors(SectionType):
    key = "advisors"
    label = "Accompagnateurs"
    position = 60
    template = "accueil/sections/advisors.html"
    anchor = "accompagnateurs"
    modifiers = "section--grisee accompagnateurs"

    class Form(forms.Form):
        kicker = forms.CharField(
            label="Surtitre", required=False, initial="Les professionnels du réseau pour l'emploi"
        )
        title = forms.CharField(label="Titre", initial="Un accompagnateur près de chez vous.")
        intro = forms.CharField(
            label="Introduction",
            required=False,
            widget=forms.Textarea,
            initial="Des professionnels habilités vous orientent et vous suivent vers l'emploi, gratuitement. Trouvez ceux de votre territoire.",
        )
        legend = forms.CharField(label="Légende des exemples", required=False, initial="Par exemple :")
        tags = ListField(
            Tag,
            label="Exemples de structures",
            min_num=1,
            max_num=8,
            initial=[
                {"icon": "ri-home-smile-2-line", "label": "Mission locale"},
                {"icon": "ri-briefcase-line", "label": "France Travail"},
                {"icon": "ri-user-shared-line", "label": "Cap emploi"},
                {"icon": "ri-government-line", "label": "Département & collectivités"},
                {"icon": "ri-community-line", "label": "Structures d'accompagnement"},
            ],
        )
        cta_label = forms.CharField(label="Bouton", initial="Trouver un accompagnateur autour de moi")
        cta_href = PlatformPath(label="Cible du bouton", initial="/search/prescribers/results")
