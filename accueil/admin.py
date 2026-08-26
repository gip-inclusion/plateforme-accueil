"""Stopgap editing UI.

The real one is `/edition/`, whose information architecture is the page rather
than the schema: a plan of the page, then a section at a time. Until it is
complete the admin still lets us reorder, hide and override sections. Its URLs
are only mounted when ADMIN_ENABLED is set.
"""

from django.contrib import admin

from accueil.forms import SectionForm, section_form_class
from accueil.models import Page, Section
from accueil.sections import registry


admin.site.site_header = "La plateforme de l'inclusion"
admin.site.site_title = "Page d'accueil"
admin.site.index_title = "Contenu de la page"


def _declared(kind):
    return {cls.key: cls for cls in registry.types()}.get(kind)


class SectionInline(admin.TabularInline):
    model = Section
    extra = 0
    fields = ("kind", "position", "active", "content")
    readonly_fields = ("kind",)
    ordering = ("position",)
    can_delete = False

    def has_add_permission(self, request, obj):
        # Rows come from `sync_sections`, so they always match a declared type.
        return False


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ("label", "slug")
    inlines = (SectionInline,)


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ("name", "position", "active", "customised")
    list_display_links = ("name",)
    list_editable = ("position", "active")
    list_filter = ("active",)
    ordering = ("position",)
    form = SectionForm

    def get_form(self, request, obj=None, **kwargs):
        # The editable fields are whatever the section type declares, so the
        # form class depends on the row being edited.
        declared = _declared(obj.kind) if obj else None
        if declared is not None:
            kwargs["form"] = section_form_class(declared)
        return super().get_form(request, obj, **kwargs)

    @admin.display(description="section", ordering="position")
    def name(self, section):
        declared = _declared(section.kind)
        return declared.label if declared else f"{section.kind} — type absent du code"

    @admin.display(description="modifié", boolean=True)
    def customised(self, section):
        return bool(section.content)
