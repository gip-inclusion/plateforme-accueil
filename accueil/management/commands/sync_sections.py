"""Create the database rows for the sections declared in the code.

Idempotent, and never destructive: a section removed from the code keeps its
row (it simply stops being rendered), so rolling a deploy back cannot lose an
editor's work.
"""

from django.core.management.base import BaseCommand

from accueil.models import Page, Section
from accueil.sections import registry


class Command(BaseCommand):
    help = "Synchronise les sections déclarées dans le code avec la base."

    def add_arguments(self, parser):
        parser.add_argument("--page", default="accueil")

    def handle(self, *args, **options):
        page, created = Page.objects.get_or_create(slug=options["page"])
        if created:
            self.stdout.write(f"page créée : {page.slug}")

        known = set()
        for section_type in registry.types():
            known.add(section_type.key)
            section, created = Section.objects.get_or_create(
                page=page,
                kind=section_type.key,
                defaults={"position": section_type.position},
            )
            if created:
                self.stdout.write(f"section créée : {section.kind} (ordre {section.position})")

        for section in Section.objects.filter(page=page).exclude(kind__in=known):
            self.stdout.write(self.style.WARNING(f"section sans type déclaré, non rendue : {section.kind}"))

        self.stdout.write(self.style.SUCCESS("sections synchronisées"))
