"""The page follows the environment that embeds it, and only ever that one."""

import re

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import override_settings

from accueil.sections.hero import Hero


PROD = settings.PLATFORM_DEFAULT_ORIGIN
DEMO = "demo.plateforme.inclusion.gouv.fr"
EMPLOI = Hero.searches["emploi"].results_path


def _links(body):
    return re.findall(r'<a\b[^>]*\bhref="(https?://[^"]+)"', body)


def test_the_page_links_to_the_default_platform_when_no_host_says_otherwise(client):
    assert all(link.startswith(PROD) for link in _links(client.get("/").content.decode()))


def test_an_announced_host_carries_every_link_with_it(client):
    links = _links(client.get("/", {"host": DEMO}).content.decode())
    assert links
    assert all(link.startswith(f"https://{DEMO}") for link in links)


def test_a_review_app_is_recognised_by_its_prefix(client):
    body = client.get("/", {"host": "c1-review-1234.cleverapps.io"}).content.decode()
    assert all(link.startswith("https://c1-review-1234.cleverapps.io") for link in _links(body))


@pytest.mark.parametrize(
    "host",
    [
        "evil.example",
        "c1-review-x.evil.cleverapps.io",  # `*` must not cross a dot
        "plateforme.inclusion.gouv.fr.evil.example",
        "evil.example/plateforme.inclusion.gouv.fr",
        "plateforme.inclusion.gouv.fr:8000@evil.example",
        "app.scalingo.io",
        "",
    ],
)
def test_an_unclaimable_host_falls_back_to_the_default(client, host):
    assert client.get("/search", {"type": "emploi", "host": host}).url == PROD + EMPLOI
    assert all(link.startswith(PROD) for link in _links(client.get("/", {"host": host}).content.decode()))


def test_the_search_lands_on_the_same_deployment_as_the_page(client):
    # The form carries the host over, so a visitor who searches from the demo
    # site stays on it instead of being thrown to production.
    assert client.get("/search", {"type": "emploi", "host": DEMO}).url == f"https://{DEMO}{EMPLOI}"


def test_the_form_carries_the_announced_host(client):
    body = client.get("/", {"host": DEMO}).content.decode()
    assert f'<input type="hidden" name="host" value="{DEMO}">' in body
    assert 'name="host"' not in client.get("/").content.decode()


def test_frame_ancestors_is_not_the_redirect_allowlist():
    # Being allowed to embed the page is not being allowed to receive its
    # visitors: a redirect launders a link behind our domain, an embed does not.
    assert "https://*.scalingo.io" in settings.SECURE_CSP["frame-ancestors"]
    assert not any("scalingo" in host for host in settings.PLATFORM_ALLOWED_HOSTS)


def test_an_editor_cannot_pin_a_link_to_one_environment():
    # A pasted absolute URL would freeze the link on whichever host the editor
    # copied it from, which is the whole defect this replaces.
    from accueil.sections.base import PlatformPath

    field = PlatformPath()
    assert field.clean("/search/employers/results") == "/search/employers/results"
    for pasted in ("https://emplois.inclusion.beta.gouv.fr/search", "search/employers", "//evil.example"):
        with pytest.raises(ValidationError):
            field.clean(pasted)


@override_settings(PLATFORM_ALLOWED_HOSTS=settings.PLATFORM_ALLOWED_HOSTS + ["localhost:*", "127.0.0.1:*"])
def test_a_local_host_is_reached_over_plain_http(client):
    # `make embed-test` serves the fake host page on another port than the app,
    # and nothing local speaks HTTPS.
    assert client.get("/search", {"type": "emploi", "host": "localhost:8001"}).url == f"http://localhost:8001{EMPLOI}"
    body = client.get("/", {"host": "127.0.0.1:8001"}).content.decode()
    assert all(link.startswith("http://127.0.0.1:8001") for link in _links(body))


def test_a_port_is_refused_on_a_public_host(client):
    # Only local development runs off-port; a port elsewhere is someone probing.
    assert client.get("/search", {"type": "emploi", "host": f"{DEMO}:8001"}).url == PROD + EMPLOI
