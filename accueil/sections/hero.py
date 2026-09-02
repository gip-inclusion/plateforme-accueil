"""Hero: headline, and the single dispatched search form."""

from typing import NamedTuple

from django import forms

from accueil.sections.base import Illustration, SectionType, registry


class SearchTarget(NamedTuple):
    """One of the hero's search types. Declared in code, not in `Form`: a
    redirect target is not editable content."""

    label_short: str
    label_long: str
    icon: str
    results_url: str


@registry.register
class Hero(SectionType):
    key = "hero"
    label = "Héros et recherche"
    position = 10
    template = "accueil/sections/hero.html"

    # Order is the tab order. Results pages, not their landing counterparts:
    # les emplois serves this very page there in an iframe, so a visitor sent
    # back would loop.
    searches = {
        "emploi": SearchTarget(
            label_short="Emploi",
            label_long="Un emploi inclusif",
            icon="ri-briefcase-line",
            results_url="https://emplois.inclusion.beta.gouv.fr/search/employers/results",
        ),
        "insertion": SearchTarget(
            label_short="Insertion",
            label_long="Un service d'insertion",
            icon="ri-compass-3-line",
            results_url="https://emplois.inclusion.beta.gouv.fr/search/services/results",
        ),
        "accompagnateur": SearchTarget(
            label_short="Accompagnateur",
            label_long="Un accompagnateur",
            icon="ri-user-line",
            results_url="https://emplois.inclusion.beta.gouv.fr/search/prescribers/results",
        ),
    }
    default_search = "emploi"

    @classmethod
    def resolve_search(cls, requested):
        """Always one of the declared keys, so an unknown "type" cannot steer
        the redirect (see accueil.views.search)."""
        return requested if requested in cls.searches else cls.default_search

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
