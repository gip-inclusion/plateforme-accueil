"""Stopgap editing UI.

The real one is `/pilotage/`, whose information architecture is the page rather
than the schema. Until then the admin lets us reorder, hide and override
sections; it is only registered when ADMIN_ENABLED is set.
"""

from django.contrib import admin

from accueil.models import Page, Section
from accueil.sections import registry


class SectionInline(admin.TabularInline):
    model = Section
    extra = 0
    fields = ("kind", "position", "active", "content")
    ordering = ("position",)


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ("label", "slug")
    inlines = (SectionInline,)


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ("kind", "label", "position", "active", "overridden")
    list_editable = ("position", "active")
    list_filter = ("active",)
    ordering = ("position",)

    @admin.display(description="nom")
    def label(self, section):
        declared = {cls.key: cls for cls in registry.types()}.get(section.kind)
        return declared.label if declared else "— type absent du code —"

    @admin.display(description="modifiée", boolean=True)
    def overridden(self, section):
        return bool(section.content)
