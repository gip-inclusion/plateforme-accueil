"""The editing UI: who gets in, and what the page must never become."""

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.urls import reverse


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
