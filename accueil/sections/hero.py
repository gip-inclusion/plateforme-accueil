"""Hero: headline, search tabs, and the three search forms."""

from django import forms

from accueil.sections.base import SectionType, registry


@registry.register
class Hero(SectionType):
    key = "hero"
    label = "Héros et recherche"
    position = 10
    template = "accueil/sections/hero.html"

    class Form(forms.Form):
        # Stored with a newline and rendered with |linebreaksbr: editor copy is
        # never marked safe, so the <br> cannot come from the field itself.
        title = forms.CharField(
            label="Titre",
            widget=forms.Textarea,
            initial="Tous les emplois, les services inclusifs,\net les accompagnateurs autour de vous",
        )
        # Reference example of an opened field: the literal moved from the
        # template to `initial`, and the template now reads `content.note`.
        # Every other string on the page is still literal, which is fine.
        note = forms.CharField(
            label="Note sous la recherche",
            widget=forms.Textarea(attrs={"rows": 3}),
            initial="Recherche libre et sans compte. Créez un compte pour postuler, orienter ou publier.",
        )
