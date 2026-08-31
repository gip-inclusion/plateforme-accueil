"""Shared shape for the two search blocks.

Jobs and services render the same markup: featured cards on one side, shortcut
pills on the other. They differ only by copy, by which column comes first, and
by the badge — so they share one template and declare the rest as data.
"""

from django import forms

from accueil.sections.base import Icon, Illustration, SectionType


class Card(forms.Form):
    title = forms.CharField(label="Titre")
    stat = forms.CharField(label="Accroche", required=False)
    text = forms.CharField(label="Texte", required=False, widget=forms.Textarea)
    icon = Icon(label="Icône")
    image = Illustration(
        label="Image",
        # .carte-media__media is widest just *below* the 64rem breakpoint, not
        # above it: at 1023px, .bloc-recherche__grille is still single-column
        # while .cartes-media is already two-up (>=30rem), so each card gets
        # (1023px viewport − 2×2rem .section padding − 1.25rem gap) / 2 ≈
        # 470px — wider than the ~360px the desktop 1.5fr/2-up arrangement
        # produces above 64rem; twice is ~939, rounded up.
        max_width=940,
        ratio=(16, 10),  # the card's frame, see .carte-media__media
    )
    href = forms.URLField(label="Lien")


class Shortcut(forms.Form):
    label = forms.CharField(label="Libellé")
    icon = Icon(label="Icône")
    href = forms.URLField(label="Lien")


class SearchSection(SectionType):
    """Base for the jobs and services blocks. Presentation only — everything
    here is a code decision, not something an editor changes."""

    template = "accueil/sections/search_block.html"
    cards_first = True
    badge_kind = ""  # drives badge--<kind> and carte-media__pastille--<kind>
    badge_label = ""
    stat_modifier = ""  # appended to carte-media__stat
