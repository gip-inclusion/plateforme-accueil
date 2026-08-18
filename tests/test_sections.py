import pytest
from django import forms
from django.template.loader import get_template

from accueil import sections
from accueil.sections.base import Registry, SectionType


def test_registry_lists_sections_in_order():
    keys = [section.key for section in sections.registry.sections()]
    assert keys == [
        "hero",
        "features",
        "figures",
        "jobs",
        "services",
        "advisors",
        "testimonials",
        "profiles",
    ]


def test_every_section_has_its_template():
    for section_type in sections.registry.types():
        get_template(section_type.template)  # raises TemplateDoesNotExist


def test_a_section_without_overrides_renders_the_code_values(client):
    # The hero note is the reference example of an opened field: it lives in
    # the form's `initial`, not in the template.
    default = sections.hero.Hero.defaults()["note"]
    assert default in client.get("/").content.decode()


class Example(SectionType):
    key = "example"
    template = "accueil/sections/hero.html"

    class Form(forms.Form):
        title = forms.CharField(initial="Titre par défaut")
        intro = forms.CharField(initial="Intro par défaut")


def test_an_override_replaces_the_default():
    section = Example({"title": "Titre édité"})
    assert section.content == {"title": "Titre édité", "intro": "Intro par défaut"}


def test_a_stale_key_is_ignored_and_reported():
    # A field removed from the form must not resurrect stale content.
    section = Example({"title": "Titre édité", "removed": "vieux texte"})
    assert "removed" not in section.content
    assert section.stale_keys == ["removed"]


def test_adding_a_field_does_not_invalidate_existing_overrides():
    # Opening a new field costs no migration and no backfill: existing
    # overrides keep working, the new field arrives at its default.
    section = Example({"title": "Titre édité"})
    assert section.content["intro"] == "Intro par défaut"


def test_registry_rejects_a_duplicate_key():
    registry = Registry()
    registry.register(Example)
    with pytest.raises(ValueError, match="déjà enregistrée"):
        registry.register(Example)


def test_registry_rejects_an_incomplete_section():
    registry = Registry()
    with pytest.raises(ValueError, match="`key` et `template`"):
        registry.register(type("Empty", (SectionType,), {}))
