"""Shared shape for the two search blocks.

Jobs and services render the same markup: featured cards on one side, shortcut
pills on the other. They differ only by copy, by which column comes first, and
by the badge — so they share one template and declare the rest as data.
"""

from django import forms

from accueil.sections.base import Illustration, SectionType


class Card(forms.Form):
    title = forms.CharField(label="Titre")
    stat = forms.CharField(label="Accroche", required=False)
    text = forms.CharField(label="Texte", required=False, widget=forms.Textarea)
    icon = forms.CharField(label="Icône")
    image = Illustration(
        label="Image",
        max_width=800,
        ratio=(16, 10),  # the card's frame, see .carte-media__media
    )
    href = forms.URLField(label="Lien")


class Shortcut(forms.Form):
    label = forms.CharField(label="Libellé")
    icon = forms.CharField(label="Icône")
    href = forms.URLField(label="Lien")


class SearchSection(SectionType):
    """Base for the jobs and services blocks. Presentation only — everything
    here is a code decision, not something an editor changes."""

    template = "accueil/sections/search_block.html"
    cards_first = True
    badge_kind = ""  # drives badge--<kind> and carte-media__pastille--<kind>
    badge_label = ""
    stat_modifier = ""  # appended to carte-media__stat
