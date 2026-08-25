"""L'édition des listes répétables, élément par élément."""

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.http import Http404

from accueil import editing
from accueil.models import Section
from accueil.sections import registry


pytestmark = pytest.mark.django_db


@pytest.fixture
def page():
    call_command("sync_sections", verbosity=0)


@pytest.fixture
def editor(page):
    return User.objects.create_user("nadia", "nadia@example.test", "x", is_staff=True)


@pytest.fixture
def testimonials(page):
    return Section.objects.get(kind="testimonials")


@pytest.fixture
def figures(page):
    return Section.objects.get(kind="figures")


def declared(kind):
    return {section_type.key: section_type for section_type in registry.types()}[kind]


def test_an_untouched_list_reads_from_the_code(testimonials):
    values = editing.list_values(testimonials, declared("testimonials"), "quotes")
    assert values[0]["name"] == "Nadia B."


def test_saving_a_changed_list_records_an_override(testimonials):
    section_type = declared("testimonials")
    values = editing.list_values(testimonials, section_type, "quotes")
    values[0]["name"] = "Ana P."
    editing.save_list(testimonials, section_type, "quotes", values)

    testimonials.refresh_from_db()
    assert testimonials.content["quotes"][0]["name"] == "Ana P."


def test_saving_a_list_back_to_the_code_values_drops_the_override(figures):
    # `figures.indicators` — not `testimonials.quotes` — is the case that
    # actually exercises the cleaned-vs-cleaned comparison in `save_list`:
    # each `Indicator` carries an `image` (an `Illustration`), so cleaning
    # injects an `image_credit: ""` on every item. Comparing the cleaned list
    # against the *raw* `initial` (rather than the cleaned default) would
    # never match, and this override would never drop.
    section_type = declared("figures")
    values = editing.list_values(figures, section_type, "indicators")
    values[0]["label"] = "un libellé changé"
    editing.save_list(figures, section_type, "indicators", values)

    editing.save_list(figures, section_type, "indicators", section_type.defaults()["indicators"])

    figures.refresh_from_db()
    assert "indicators" not in figures.content


def test_a_list_that_breaks_its_own_rules_is_refused(testimonials):
    # `quotes` déclare min_num=1 : la liste ne peut pas devenir vide.
    with pytest.raises(ValidationError):
        editing.save_list(testimonials, declared("testimonials"), "quotes", [])
    testimonials.refresh_from_db()
    assert "quotes" not in testimonials.content


def test_an_unknown_list_name_is_a_404_not_a_500(testimonials):
    section_type = declared("testimonials")
    with pytest.raises(Http404):
        editing.list_values(testimonials, section_type, "does_not_exist")
    with pytest.raises(Http404):
        editing.save_list(testimonials, section_type, "does_not_exist", [])


def test_a_non_list_field_name_is_a_404_not_a_wrongly_saved_string(testimonials):
    # Without the guard, `Form.base_fields["title"].clean(["a", "b"])` returns
    # the *string* "['a', 'b']", which would then save straight into `content`
    # (`Section.clean`, the model-level guard, is never run by `save_list`).
    section_type = declared("testimonials")
    with pytest.raises(Http404):
        editing.save_list(testimonials, section_type, "title", ["a", "b"])
    with pytest.raises(Http404):
        editing.list_values(testimonials, section_type, "title")

    testimonials.refresh_from_db()
    assert "title" not in testimonials.content


def test_a_malformed_content_column_does_not_crash_the_helpers(testimonials):
    # `SectionType.__init__` already tolerates a non-dict `content`; these
    # helpers are meant to be a foundation as solid, not a step down from it.
    # A list, not `None`: the column is `NOT NULL`, so a JSON list is the
    # smallest malformed-but-storable value to exercise the guard against.
    testimonials.content = []
    testimonials.save(update_fields=["content"])

    section_type = declared("testimonials")
    values = editing.list_values(testimonials, section_type, "quotes")
    assert values[0]["name"] == "Nadia B."

    editing.save_list(testimonials, section_type, "quotes", values)
    testimonials.refresh_from_db()
    assert "quotes" not in (testimonials.content or {})
