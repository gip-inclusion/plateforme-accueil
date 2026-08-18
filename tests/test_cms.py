from unittest import mock

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.test import override_settings

from accueil import content
from accueil.models import Page, Section
from accueil.sections import registry


# Every test here needs the database; the suite skips them when it is absent.
pytestmark = pytest.mark.django_db


@pytest.fixture
def page():
    call_command("sync_sections", verbosity=0)
    return Page.objects.get(slug="accueil")


def test_sync_creates_one_row_per_declared_section(page):
    assert set(Section.objects.values_list("kind", flat=True)) == {
        section_type.key for section_type in registry.types()
    }


def test_sync_is_idempotent(page):
    call_command("sync_sections", verbosity=0)
    assert Section.objects.count() == len(registry.types())


def test_sync_keeps_a_section_removed_from_the_code(page):
    # A rolled-back deploy must not lose an editor's work.
    Section.objects.create(page=page, kind="gone", position=999)
    call_command("sync_sections", verbosity=0)
    assert Section.objects.filter(kind="gone").exists()


def test_without_overrides_the_page_renders_the_code(page, client):
    default = registry.sections()[0].content["note"]
    assert default in client.get("/").content.decode()


def test_an_override_replaces_the_code_text(page, client):
    Section.objects.filter(kind="hero").update(content={"note": "Texte piloté depuis la base."})
    assert "Texte piloté depuis la base." in client.get("/").content.decode()


def test_a_disabled_section_disappears(page, client):
    assert "temoignage" in client.get("/").content.decode()
    Section.objects.filter(kind="testimonials").update(active=False)
    cache.clear()  # otherwise the overrides pointer still serves the old value
    assert "temoignage" not in client.get("/").content.decode()


def test_overrides_are_cached_briefly(page, client):
    client.get("/")
    Section.objects.filter(kind="testimonials").update(active=False)
    # Deliberate: serverless instances cannot invalidate each other's local
    # cache, so a change takes effect within OVERRIDES_CACHE_TTL, not instantly.
    assert "temoignage" in client.get("/").content.decode()


def test_database_position_wins_over_the_code(page):
    Section.objects.filter(kind="profiles").update(position=5)
    assert [section.key for section in content.page_sections()][0] == "profiles"


@override_settings(DATABASE_CONFIGURED=False)
def test_without_a_database_the_page_renders_the_defaults(client):
    response = client.get("/")
    assert response.status_code == 200
    assert registry.sections()[0].content["note"] in response.content.decode()


def test_an_unreachable_database_falls_back_to_the_defaults(page, client):
    with mock.patch("accueil.models.Section.objects.filter", side_effect=OSError("connexion refusée")):
        response = client.get("/")
    assert response.status_code == 200
    assert registry.sections()[0].content["note"] in response.content.decode()
