"""The editing UI: who gets in, and what the page must never become."""

import io
import json

import pytest
from django.conf import settings
from django.contrib.auth import get_user
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.shortcuts import resolve_url
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from pytest_django.asserts import assertRedirects

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
    for field in ('name="kicker"', 'name="title"', 'name="intro"'):
        assert field in body
    # `steps` is a `ListField`: it is edited item by item on the board below
    # the form (Task 11), not as a field of the form itself.
    assert 'name="steps"' not in body


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
    # `/edition/`'s own section screen no longer carries a list as a form
    # field (Task 11: it is edited item by item on the board instead), so
    # this can no longer be exercised through the real screen. `ListEditor`
    # itself — the admin's JSON textarea, `section_form_class`'s default
    # (`with_lists=True`) — still validates the same way; this is the one
    # place left that checks it does.
    from accueil.forms import section_form_class
    from accueil.models import Section
    from accueil.sections.features import Features

    section = Section.objects.get(kind="features")
    data = {"position": section.position, "active": "on"}
    for name, value in Features.defaults().items():
        data[name] = json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value
    data["steps"] = "{pas du json"

    form = section_form_class(Features)(data, instance=section)
    assert not form.is_valid()
    assert "JSON invalide" in str(form.errors["steps"])

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
    OIDC_PROVIDER_URL="http://testserver",
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
def test_sso_user_creation(db):
    backend = _backend()
    user = backend.create_user({"email": "bob@example.test", "given_name": "Bob", "usual_name": "Beauregard"})
    assert not user.is_staff
    assert not user.is_superuser
    assert user.first_name == "Bob"
    assert user.last_name == "Beauregard"


@oidc_configured
def test_sso_user_update(db):
    User.objects.create(email="bob@example.test", first_name="bad", last_name="bad", is_staff=True, is_superuser=True)
    backend = _backend()
    user = backend.create_user({"email": "bob@example.test", "given_name": "Bob", "usual_name": "Beauregard"})
    # These are updated
    assert user.first_name == "Bob"
    assert user.last_name == "Beauregard"
    # There are not updated
    assert user.is_staff
    assert user.is_superuser


@oidc_configured
def test_auto_login(db, client):
    response = client.get(reverse("edition:plan"))
    assertRedirects(
        response, reverse("oidc_authentication_init") + "?next=%2Fedition%2F", fetch_redirect_response=False
    )


@oidc_configured
def test_admin_auto_login(db, client):
    response = client.get(reverse("admin:index"))
    expected_url = reverse("admin:login") + "?next=%2Fadmin%2F"
    assertRedirects(response, expected_url, fetch_redirect_response=False)

    response = client.get(expected_url)
    # We don't keep the next parameter as it's not used in the oidc callback
    assertRedirects(response, reverse("oidc_authentication_init"), fetch_redirect_response=False)


@oidc_configured
def test_logout(db, client):
    user = User.objects.create(
        email="bob@example.test", first_name="bad", last_name="bad", is_staff=True, is_superuser=True
    )
    client.force_login(user)

    response = client.post(reverse("logout"))
    assertRedirects(response, reverse("index"))

    assert get_user(client).is_authenticated is False


@oidc_configured
def test_admin_logout(db, client):
    user = User.objects.create(
        email="bob@example.test", first_name="bad", last_name="bad", is_staff=True, is_superuser=True
    )
    client.force_login(user)

    response = client.post(reverse("admin:logout"))
    assertRedirects(response, reverse("index"))

    assert get_user(client).is_authenticated is False


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


def test_the_admin_is_never_framable(client, editor):
    # The public CSP lets *.cleverapps.io and *.scalingo.io embed the showcase
    # page; anyone can host there, so the admin must not inherit that policy.
    client.force_login(editor)
    response = client.get("/admin/")
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_the_admin_login_page_is_never_framable(client):
    response = client.get("/admin/login/")
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_a_section_upload_travels_through_the_editing_screen(client, editor, tmp_path, settings):
    # Le champ image ne sert à rien si le gabarit n'est pas `multipart` ou si la
    # vue ne lit pas `request.FILES` : le bouton s'affiche, et rien n'arrive.
    settings.MEDIA_ROOT = tmp_path
    settings.UPLOADS_ENABLED = True
    client.force_login(editor)
    row = Section.objects.get(kind="testimonials")
    url = reverse("edition:section", args=[row.pk])

    response = client.get(url)
    assert 'enctype="multipart/form-data"' in response.content.decode()

    form = response.context["form"]
    data = {bound.name: bound.value() if bound.value() is not None else "" for bound in form}
    data["illustration_current"] = "accueil/img/temoignages-illustration.webp"

    buffer = io.BytesIO()
    Image.new("RGB", (1200, 700), (10, 20, 30)).save(buffer, format="PNG")
    data["illustration"] = SimpleUploadedFile("neuf.png", buffer.getvalue(), content_type="image/png")

    assert client.post(url, data).status_code == 302
    row.refresh_from_db()
    assert row.content["illustration"].startswith("uploads/")


def test_an_illustration_error_is_associated_with_its_field(client, editor, tmp_path, settings):
    # `aria-describedby` sur le champ fichier ne sert à rien si rien sur la
    # page ne porte réellement cet id : `edition/section.html` doit rendre le
    # paragraphe d'erreur avec l'id que Django attend, pas seulement à côté du
    # champ visuellement.
    settings.MEDIA_ROOT = tmp_path
    settings.UPLOADS_ENABLED = True
    client.force_login(editor)
    row = Section.objects.get(kind="testimonials")
    url = reverse("edition:section", args=[row.pk])

    form = client.get(url).context["form"]
    data = {bound.name: bound.value() if bound.value() is not None else "" for bound in form}
    data["illustration_current"] = "accueil/img/temoignages-illustration.webp"
    data["illustration"] = SimpleUploadedFile("cv.pdf", b"%PDF-1.4", content_type="application/pdf")

    response = client.post(url, data)
    assert response.status_code == 200
    body = response.content.decode()
    assert 'aria-describedby="id_illustration_helptext id_illustration_error"' in body
    assert 'id="id_illustration_error"' in body


def test_saving_a_section_keeps_overrides_the_form_does_not_carry(client, editor):
    # `quotes` is still declared on `Testimonials.Form` — so `Section.clean`
    # (the model) still validates it at every save — but Task 11 removes it
    # from the *generated* form for good: it is edited item by item on the
    # board below, not as a field here. Saving the section's other fields
    # must leave this override untouched, exercising `SectionForm.clean`'s
    # `name in self.fields` guard through the real screen, not a form built
    # by hand.
    from accueil.sections.testimonials import Testimonials

    client.force_login(editor)
    row = Section.objects.get(kind="testimonials")
    row.content = {"quotes": [{"quote": "Épatant.", "name": "Ana", "role": ""}]}
    row.save()

    defaults = Testimonials.defaults()
    data = {
        "position": row.position,
        "active": "on",
        "kicker": defaults["kicker"],
        "title": "Un autre titre.",
        "illustration_current": defaults["illustration"],
        "illustration_credit": "",
    }
    response = client.post(reverse("edition:section", args=[row.pk]), data)
    assert response.status_code == 302

    row.refresh_from_db()
    assert row.content["title"] == "Un autre titre."
    assert row.content["quotes"][0]["name"] == "Ana"


def test_a_stale_key_still_saves_and_is_dropped(client, editor):
    from accueil.sections.testimonials import Testimonials

    # Contrairement à `quotes` dans le test ci-dessus (déplacée, mais toujours
    # déclarée dans `Testimonials.Form.base_fields`), une clé que le code ne
    # déclare plus du tout doit continuer à être écartée à chaque
    # enregistrement — comme avant cette tâche. `Section.clean` (modèle) la
    # rejette de toute façon à chaque sauvegarde ; la garder ferait planter
    # l'écran d'édition (500), pas juste échouer la validation.
    client.force_login(editor)
    row = Section.objects.get(kind="testimonials")
    row.content = {"vestige": "un champ disparu du code"}
    row.save()

    url = reverse("edition:section", args=[row.pk])
    form = client.get(url).context["form"]
    data = {}
    for bound in form:
        value = bound.value()
        data[bound.name] = value if value is not None else ""
    data["illustration_current"] = Testimonials.defaults()["illustration"]
    data["title"] = "Un autre titre."

    assert client.post(url, data).status_code == 302

    row.refresh_from_db()
    assert row.content["title"] == "Un autre titre."
    assert "vestige" not in row.content


def test_posting_the_default_value_clears_the_override(client, editor):
    # Le garde de `SectionForm.clean` (ce qui a remplacé la reconstruction
    # totale de `content`) doit continuer à effacer un override quand
    # l'autrice retape le texte du code dans un champ que le formulaire porte
    # bien : sans lui, `content` garderait la valeur périmée pour toujours et
    # ce champ cesserait de suivre les changements du code.
    from accueil.sections.features import Features

    client.force_login(editor)
    section = Section.objects.get(kind="features")
    section.content = {"title": "Ancien titre personnalisé."}
    section.save()

    data = {"position": section.position, "active": "on"}
    for name, value in Features.defaults().items():
        data[name] = json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value

    assert client.post(reverse("edition:section", args=[section.pk]), data).status_code == 302
    section.refresh_from_db()
    assert section.content == {}


def test_saving_an_unchanged_list_with_an_illustration_adds_no_override(client, editor):
    # Regression: `SectionForm.clean` used to compare the cleaned list against
    # the *raw* default. Cleaning `figures.indicators` injects an
    # `image_credit: ""` on every item (each `Indicator.image` is an
    # `Illustration`), so the cleaned list and the raw default never matched —
    # saving the section with nothing changed wrote a spurious `indicators`
    # override, which then stopped following pull requests.
    from accueil.sections.figures import Figures

    client.force_login(editor)
    section = Section.objects.get(kind="figures")
    data = {"position": section.position, "active": "on"}
    for name, value in Figures.defaults().items():
        data[name] = json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value

    assert client.post(reverse("edition:section", args=[section.pk]), data).status_code == 302
    section.refresh_from_db()
    assert section.content == {}
