"""L'édition des listes répétables, élément par élément."""

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command

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


def test_saving_a_list_back_to_the_code_values_drops_the_override(testimonials):
    section_type = declared("testimonials")
    values = editing.list_values(testimonials, section_type, "quotes")
    values[0]["name"] = "Ana P."
    editing.save_list(testimonials, section_type, "quotes", values)

    editing.save_list(testimonials, section_type, "quotes", section_type.defaults()["quotes"])

    testimonials.refresh_from_db()
    assert "quotes" not in testimonials.content


def test_a_list_that_breaks_its_own_rules_is_refused(testimonials):
    # `quotes` déclare min_num=1 : la liste ne peut pas devenir vide.
    with pytest.raises(ValidationError):
        editing.save_list(testimonials, declared("testimonials"), "quotes", [])
    testimonials.refresh_from_db()
    assert "quotes" not in testimonials.content
