"""Quotes from users of the platform."""

from accueil.sections.base import SectionType, registry


@registry.register
class Testimonials(SectionType):
    key = "testimonials"
    label = "Témoignages"
    position = 70
    template = "accueil/sections/testimonials.html"
