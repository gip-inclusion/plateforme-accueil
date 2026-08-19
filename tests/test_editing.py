"""The editing UI: who gets in, and what the page must never become."""

import json

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.shortcuts import resolve_url
from django.test import override_settings
from django.urls import reverse

from accueil.models import Section


pytestmark = pytest.mark.django_db


@pytest.fixture
def page():
    call_command("sync_sections", verbosity=0)


@pytest.fixture
def editor(page):
    return User.objects.create_user("nadia", "nadia@example.test", "x", is_staff=True)


def test_the_plan_needs_an_account(client, page):
    response = client.get("/edition/")
    assert response.status_code == 302
    assert "/edition/" not in response["Location"].split("?")[0]


def test_a_visitor_without_staff_is_refused(client, page):
    User.objects.create_user("bob", "bob@example.test", "x")
    client.login(username="bob", password="x")
    assert client.get("/edition/").status_code == 302


def test_an_editor_sees_the_page_in_order(client, editor):
    client.force_login(editor)
    body = client.get("/edition/").content.decode()
    for label in ("Héros et recherche", "Chiffres clés", "Parcours par profil"):
        assert label in body
    # Recognisable by content, not by type.
    assert "Ça se passe sur La plateforme de l&#x27;inclusion." in body


def test_the_editing_ui_is_never_embeddable(client, editor):
    # The public page is meant to be framed; this one must never be.
    client.force_login(editor)
    response = client.get("/edition/")
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_the_public_page_stays_embeddable(client):
    response = client.get("/")
    assert "X-Frame-Options" not in response.headers
    assert "inclusion.gouv.fr" in response.headers["Content-Security-Policy"]


def test_moving_a_section_reorders_the_page(client, editor):
    from accueil.models import Section

    client.force_login(editor)
    second = Section.objects.order_by("position")[1]
    client.post(reverse("edition:move", args=[second.pk]), {"direction": "up"})
    assert Section.objects.order_by("position").first().kind == second.kind


def test_moving_the_first_section_up_does_nothing(client, editor):
    from accueil.models import Section

    client.force_login(editor)
    first = Section.objects.order_by("position").first()
    client.post(reverse("edition:move", args=[first.pk]), {"direction": "up"})
    assert Section.objects.order_by("position").first().pk == first.pk


def test_hiding_a_section_removes_it_from_the_page(client, editor):
    from accueil.models import Section

    client.force_login(editor)
    section = Section.objects.get(kind="testimonials")
    client.post(reverse("edition:toggle", args=[section.pk]))
    assert "temoignage" not in client.get("/").content.decode()


def test_the_controls_refuse_a_get(client, editor):
    from accueil.models import Section

    client.force_login(editor)
    section = Section.objects.get(kind="testimonials")
    assert client.get(reverse("edition:toggle", args=[section.pk])).status_code == 405


def test_the_editor_shows_the_declared_fields(client, editor):
    from accueil.models import Section

    client.force_login(editor)
    section = Section.objects.get(kind="features")
    body = client.get(reverse("edition:section", args=[section.pk])).content.decode()
    for field in ('name="kicker"', 'name="title"', 'name="intro"', 'name="steps"'):
        assert field in body


def test_saving_stores_only_the_change(client, editor):
    from accueil.models import Section
    from accueil.sections.features import Features

    client.force_login(editor)
    section = Section.objects.get(kind="features")
    data = {"position": section.position, "active": "on"}
    for name, value in Features.defaults().items():
        data[name] = json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value
    data["title"] = "Un titre revu"

    response = client.post(reverse("edition:section", args=[section.pk]), data)
    assert response.status_code == 302
    section.refresh_from_db()
    assert section.content == {"title": "Un titre revu"}
    assert "Un titre revu" in client.get("/").content.decode()


def test_an_invalid_list_is_reported_not_saved(client, editor):
    from accueil.models import Section
    from accueil.sections.features import Features

    client.force_login(editor)
    section = Section.objects.get(kind="features")
    data = {"position": section.position, "active": "on"}
    for name, value in Features.defaults().items():
        data[name] = json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value
    data["steps"] = "{pas du json"

    response = client.post(reverse("edition:section", args=[section.pk]), data)
    assert response.status_code == 200  # redisplayed with the error
    assert "JSON invalide" in response.content.decode()
    section.refresh_from_db()
    assert section.content == {}


def test_an_overridden_field_is_flagged_and_can_be_reverted(client, editor):
    from accueil.models import Section

    client.force_login(editor)
    section = Section.objects.get(kind="features")
    section.content = {"title": "Un titre revu"}
    section.save()

    body = client.get(reverse("edition:section", args=[section.pk])).content.decode()
    assert "Revenir au texte du code" in body

    client.post(reverse("edition:reset-field", args=[section.pk, "title"]))
    section.refresh_from_db()
    assert section.content == {}
    # The page follows the code again.
    assert "Un titre revu" not in client.get("/").content.decode()


def test_the_editor_refuses_an_unknown_section(client, editor):
    from accueil.models import Page, Section

    client.force_login(editor)
    orphan = Section.objects.create(page=Page.objects.get(slug="accueil"), kind="disparue", position=999)
    response = client.get(reverse("edition:section", args=[orphan.pk]), follow=True)
    assert "n&#x27;existe plus dans le code" in response.content.decode()


def test_the_editing_ui_is_not_mounted_when_nobody_can_sign_in():
    """The default production config has neither the admin nor OIDC.

    /edition/ used to be mounted anyway, and any hit on it 500'd: the login
    redirect had nowhere to point. Not routable is the honest answer.
    """
    import importlib

    from django.urls import Resolver404, clear_url_caches, resolve

    import config.urls

    try:
        with override_settings(ADMIN_ENABLED=False, OIDC_ENABLED=False):
            importlib.reload(config.urls)
            clear_url_caches()
            with pytest.raises(Resolver404):
                resolve("/edition/")
            # The public page is untouched by any of this.
            assert resolve("/").view_name == "index"
    finally:
        # Restored only once the real settings are back, or every later test
        # inherits a URLconf without /edition/.
        importlib.reload(config.urls)
        clear_url_caches()


def test_the_plan_redirects_to_the_configured_login(client, page):
    response = client.get("/edition/")
    assert response.status_code == 302
    assert response["Location"].startswith(resolve_url(settings.LOGIN_URL))


def test_a_405_still_denies_framing(client, editor):
    from accueil.models import Section

    # The 405 must not escape the header decorators and fall back to the
    # public, embeddable policy.
    client.force_login(editor)
    section = Section.objects.get(kind="testimonials")
    response = client.get(reverse("edition:toggle", args=[section.pk]))
    assert response.status_code == 405
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_an_anonymous_get_reveals_nothing(client, page):
    from accueil.models import Section

    # Authentication is checked before the method, so an anonymous probe cannot
    # tell an existing endpoint from a missing one.
    section = Section.objects.get(kind="testimonials")
    assert client.get(reverse("edition:toggle", args=[section.pk])).status_code == 302


def test_an_unknown_section_is_a_404_not_a_500(client, editor):
    client.force_login(editor)
    assert client.post(reverse("edition:toggle", args=[999999])).status_code == 404


# The backend refuses to instantiate without a full OIDC configuration; these
# are the endpoints it checks for, pointing nowhere since nothing is fetched.
oidc_configured = override_settings(
    OIDC_RP_CLIENT_ID="test",
    OIDC_RP_CLIENT_SECRET="test",
    OIDC_RP_SIGN_ALGO="RS256",
    OIDC_OP_TOKEN_ENDPOINT="https://exemple.test/token/",
    OIDC_OP_USER_ENDPOINT="https://exemple.test/userinfo/",
    OIDC_OP_JWKS_ENDPOINT="https://exemple.test/jwks/",
)


def _backend():
    from accueil.auth import AuthentikBackend

    return AuthentikBackend()


@oidc_configured
def test_losing_the_group_downgrades_the_account(db):
    from django.contrib.auth.models import User

    backend = _backend()
    claims = {"email": "nadia@example.test", "groups": ["accueil-redaction", "accueil-publication"]}
    user = backend.create_user(claims)
    assert user.is_staff and user.groups.count() == 2

    # Same person, next login, removed from the group upstream.
    user = backend.update_user(user, {"email": "nadia@example.test", "groups": []})
    assert not user.is_staff
    assert user.groups.count() == 0
    assert not User.objects.get(pk=user.pk).is_staff


@oidc_configured
def test_sso_never_grants_superuser(db):
    from django.contrib.auth.models import User

    # An account matched on email must not inherit local superuser rights.
    local = User.objects.create_superuser("chef", "chef@example.test", "x")
    backend = _backend()
    user = backend.update_user(local, {"email": "chef@example.test", "groups": ["accueil-redaction"]})
    assert not user.is_superuser
    assert user.is_staff


@oidc_configured
def test_a_string_groups_claim_grants_nothing(db):
    backend = _backend()
    user = backend.create_user({"email": "bob@example.test", "groups": "accueil-redaction"})
    assert not user.is_staff


def test_the_public_page_never_loads_the_editing_theme(client):
    # Two CSS worlds: the house theme dresses /edition/, the public page keeps
    # its own hand-written stylesheet and must not pull in a Bootstrap build.
    body = client.get("/").content.decode()
    assert "theme-inclusion" not in body
    assert "accueil/css/main.css" in body


def test_the_editing_ui_uses_the_house_theme(client, editor):
    client.force_login(editor)
    body = client.get("/edition/").content.decode()
    assert "vendor/theme-inclusion/stylesheets/app.css" in body


def test_no_template_comment_leaks_into_the_page(client, editor):
    # `{# … #}` is single-line only in Django: spread it over two and the text
    # is rendered to the reader.
    client.force_login(editor)
    for url in ("/edition/", reverse("edition:section", args=[Section.objects.first().pk])):
        body = client.get(url).content.decode()
        assert "{#" not in body
        assert "PROVENANCE" not in body
        assert "{% comment" not in body
