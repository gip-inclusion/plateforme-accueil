"""Featured support themes, mirrored layout."""

from django import forms

from accueil.sections.base import SectionType, registry


@registry.register
class Services(SectionType):
    key = "services"
    label = "Bloc de recherche — Services"
    position = 50
    template = "accueil/sections/services.html"

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
