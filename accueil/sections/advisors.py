"""Call to action towards the prescriber search."""

from django import forms

from accueil.sections.base import SectionType, registry


@registry.register
class Advisors(SectionType):
    key = "advisors"
    label = "Accompagnateurs"
    position = 60
    template = "accueil/sections/advisors.html"

    class Form(forms.Form):
        kicker = forms.CharField(
            label="Surtitre",
            required=False,
            initial="Les professionnels du réseau pour l'emploi",
        )
        title = forms.CharField(
            label="Titre",
            initial="Un accompagnateur près de chez vous.",
        )
        intro = forms.CharField(
            label="Introduction",
            required=False,
            widget=forms.Textarea,
            initial="Des professionnels habilités vous orientent et vous suivent vers l'emploi, gratuitement. Trouvez ceux de votre territoire.",
        )
