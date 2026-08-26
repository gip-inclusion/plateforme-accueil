import pytest
from django import forms
from django.core.exceptions import ValidationError
from django.template.loader import get_template
from django.utils.html import escape

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


def _displayed(section_type, content):
    """(name, text) for every declared default the page is meant to show.

    Walks the declarations rather than the values, so that references — ids the
    page consumes but never prints — can be skipped.
    """
    for name, field in section_type.Form.base_fields.items():
        if isinstance(field, sections.ListField):
            for item in content.get(name) or []:
                for sub_name, sub_field in field.item_form.base_fields.items():
                    if isinstance(sub_field, (sections.Reference, sections.Credit)):
                        continue
                    yield f"{name}.{sub_name}", item.get(sub_name)
        elif not isinstance(field, (sections.Reference, sections.Credit)):
            yield name, content.get(name)


def test_every_opened_field_renders_its_default(client):
    # Whatever a section declares must actually reach the page: a field whose
    # template variable was forgotten would otherwise sit there editable and
    # inert. Compared escaped, since Django escapes the apostrophes.
    body = client.get("/").content.decode()
    for section in sections.registry.sections():
        for name, value in _displayed(type(section), section.content):
            if not isinstance(value, str):
                continue  # numbers are reformatted before display
            for line in value.split("\n"):  # the hero title is multi-line
                assert escape(line) in body, f"{section.key}.{name}"


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


class Item(forms.Form):
    label = forms.CharField()


def test_list_field_validates_each_item():
    field = sections.ListField(Item)
    assert field.clean([{"label": "Un"}, {"label": "Deux"}]) == [{"label": "Un"}, {"label": "Deux"}]


def test_list_field_rejects_an_invalid_item():
    field = sections.ListField(Item)
    with pytest.raises(ValidationError, match="Élément 2"):
        field.clean([{"label": "Un"}, {"label": ""}])


def test_list_field_rejects_a_non_list():
    with pytest.raises(ValidationError, match="liste"):
        sections.ListField(Item).clean({"label": "Un"})


def test_list_field_enforces_its_bounds():
    with pytest.raises(ValidationError, match="au moins"):
        sections.ListField(Item, min_num=2).clean([{"label": "Un"}])
    with pytest.raises(ValidationError, match="au plus"):
        sections.ListField(Item, max_num=1).clean([{"label": "Un"}, {"label": "Deux"}])


def test_list_field_treats_empty_as_no_items():
    assert sections.ListField(Item).clean(None) == []


def test_the_two_search_blocks_share_one_template():
    jobs, services = sections.jobs.Jobs, sections.services.Services
    assert jobs.template == services.template
    # They differ only in presentation, declared rather than forked into a
    # second template.
    assert jobs.cards_first != services.cards_first
    assert (jobs.badge_kind, services.badge_kind) == ("emploi", "service")


def test_a_list_item_rejects_a_value_of_the_wrong_kind():
    # Without the per-item check a dict lands on the page as "{'deep': [1, 2]}".
    field = sections.ListField(Item)
    with pytest.raises(ValidationError, match="doit être du texte"):
        field.clean([{"label": {"deep": [1, 2]}}])


def test_a_text_field_rejects_a_number():
    with pytest.raises(ValidationError, match="doit être du texte"):
        sections.hero.Hero.clean_value("note", 42)


def test_a_number_field_rejects_a_boolean():
    field = sections.registry.types()[2].Form.base_fields["indicators"]
    with pytest.raises(ValidationError, match="nombre entier"):
        field.clean([{"key": "x", "label": "l", "image": "i", "fallback": True}])


def test_duplicate_slugs_are_refused():
    # They become HTML ids: a duplicate breaks the tabs and the ARIA wiring.
    from accueil.sections.profiles import Profiles

    profiles = Profiles.defaults()["profiles"]
    profiles[1]["slug"] = profiles[0]["slug"]
    with pytest.raises(ValidationError, match="différent pour chaque"):
        Profiles.clean_value("profiles", profiles)


def test_a_reference_rejects_a_space():
    from accueil.sections.profiles import Profiles

    profiles = Profiles.defaults()["profiles"]
    profiles[0]["slug"] = "pro conseil"
    with pytest.raises(ValidationError, match="Élément 1"):
        Profiles.clean_value("profiles", profiles)


def test_every_declared_list_validates_its_own_defaults():
    # A declaration that raises `min_num` without extending `initial`, adds
    # `unique=` over duplicate defaults, or adds a required item subfield
    # would otherwise only surface once an editor tried to save that
    # section's list — presented as though the editor's edit were at fault,
    # when the bug is in the code's own default. Cleaning here, once, in the
    # suite, turns that into a red test instead.
    for section_type in sections.registry.types():
        for name, field in section_type.Form.base_fields.items():
            if isinstance(field, sections.ListField):
                field.clean(field.initial)  # raises ValidationError if the code's own default is invalid
