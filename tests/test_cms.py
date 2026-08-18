from unittest import mock

import pytest
from django.apps import apps
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.management import call_command
from django.test import override_settings
from django.utils.html import escape

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
    cache.clear()  # `update()` fires no signal, so the cache still holds
    assert "temoignage" not in client.get("/").content.decode()


def test_saving_a_section_shows_up_at_once(page, client):
    assert "temoignage" in client.get("/").content.decode()
    section = Section.objects.get(kind="testimonials")
    section.active = False
    section.save()
    assert "temoignage" not in client.get("/").content.decode()


def test_a_queryset_update_still_waits_for_the_cache(page, client):
    client.get("/")
    # `update()` bypasses signals, and another instance's cache cannot be
    # invalidated anyway: OVERRIDES_CACHE_TTL remains the upper bound.
    Section.objects.filter(kind="testimonials").update(active=False)
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


def test_the_admin_is_installed_in_tests():
    # Guards the two tests below: without this the admin gate would make them
    # pass vacuously.
    assert apps.is_installed("django.contrib.admin")


def test_the_admin_requires_a_login(client):
    response = client.get("/admin/", follow=False)
    assert response.status_code == 302
    assert "/admin/login/" in response["Location"]


def test_the_public_page_sets_no_cookie(client):
    # The page is embedded in an iframe: adding sessions and CSRF for the admin
    # must not start setting cookies on the public page.
    assert client.get("/").cookies == {}


def test_the_admin_is_off_by_default_outside_debug(monkeypatch):
    # A deploy must never expose a login form backed by local passwords.
    monkeypatch.delenv("ADMIN_ENABLED", raising=False)
    monkeypatch.delenv("DEBUG", raising=False)
    import importlib

    import config.settings

    reloaded = importlib.reload(config.settings)
    assert reloaded.ADMIN_ENABLED is False
    importlib.reload(config.settings)  # restore the module for the rest of the suite


def test_a_malformed_override_does_not_break_the_page(page, client):
    # The page must render whatever ended up in the database — that rule is
    # older than the CMS and must survive it.
    for garbage in ([1, 2], "texte", 42, {"cards": 5}, {"kicker": []}):
        Section.objects.filter(kind="jobs").update(content=garbage)
        cache.clear()
        assert client.get("/").status_code == 200, garbage


def test_an_unusable_override_falls_back_to_the_code(page, client):
    Section.objects.filter(kind="jobs").update(content={"kicker": []})
    cache.clear()
    default = registry.sections()[3].content["kicker"]
    assert escape(default) in client.get("/").content.decode()


def test_saving_an_unknown_field_is_refused(page):
    section = Section.objects.get(kind="jobs")
    section.content = {"inexistant": "x"}
    with pytest.raises(DjangoValidationError, match="n'existe pas"):
        section.full_clean()


def test_saving_a_javascript_url_is_refused(page):
    section = Section.objects.get(kind="jobs")
    section.content = {"see_all_href": "javascript:alert(1)"}
    with pytest.raises(DjangoValidationError, match="see_all_href"):
        section.full_clean()


def test_a_javascript_url_never_reaches_the_page(page, client):
    # Belt and braces: even written straight to the column, it is dropped.
    Section.objects.filter(kind="jobs").update(content={"see_all_href": "javascript:alert(1)"})
    cache.clear()
    assert "javascript:alert(1)" not in client.get("/").content.decode()
