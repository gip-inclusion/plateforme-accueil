"""Hero: headline, search tabs, and the three search forms."""

from django import forms

from accueil.sections.base import Illustration, SectionType, registry


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
        # Opened because this is the field the upload feature exists for: an
        # editor needs to replace the hero photo without a code change, unlike
        # the copy around it.
        visual = Illustration(
            label="Visuel",
            # .hero__visuel caps at max-width: 26rem (416px); twice is 832,
            # rounded up.
            max_width=840,
            ratio=(3, 2),
            initial="accueil/img/hero.webp",
        )
        # Reference example of a field opened beyond the kicker/title/intro
        # trio that CLAUDE.md opens everywhere by default: the literal moved
        # from the template to `initial`, and the template now reads
        # `content.note`.
        note = forms.CharField(
            label="Note sous la recherche",
            widget=forms.Textarea(attrs={"rows": 3}),
            initial="Recherche libre et sans compte. Créez un compte pour postuler, orienter ou publier.",
        )
