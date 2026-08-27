import io
import json
from unittest import mock

from django.utils.html import escape


def test_index_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.content.decode()
    assert "<title>La plateforme de l'inclusion</title>" in body
    # Escaped: the sentence now comes from a section field, and Django escapes
    # the apostrophe.
    assert escape("Des services utiles à tous les pros du Réseau pour l'emploi.") in body


def test_figures_come_from_the_feed(client):
    # Numbers come from the (mocked) key-figures feed, formatted for French.
    body = client.get("/").content.decode().replace(" ", " ")
    assert "12 345" in body  # offres_ouvertes
    assert "200 000" in body  # services_di
    assert "6 000" in body  # prescripteurs_actifs


def test_cities_proxy_maps_slug_and_label(client):
    feed = {
        "results": [
            {"text": "Lyon (69)", "id": "lyon-69"},
            {"text": "Lyon 1er (69)", "id": "lyon-1er-69"},
        ]
    }
    with mock.patch(
        "urllib.request.urlopen",
        side_effect=lambda *a, **k: io.BytesIO(json.dumps(feed).encode()),
    ):
        data = client.get("/api/cities?q=lyon").json()
    assert data["results"][0] == {"slug": "lyon-69", "label": "Lyon (69)"}
    assert len(data["results"]) == 2


def test_cities_empty_query(client):
    # No query -> no upstream call, empty list.
    assert client.get("/api/cities").json() == {"results": []}


def test_hero_targets_the_three_searches(client):
    body = client.get("/").content.decode()
    assert "emplois.inclusion.beta.gouv.fr/search/employers" in body
    assert "emplois.inclusion.beta.gouv.fr/search/prescribers" in body
    assert "emplois.inclusion.beta.gouv.fr/search/services" in body
    assert 'name="category"' in body  # services thematic select
    assert 'value="creer-une-entreprise"' in body


def test_figures_fall_back_when_feed_is_down(client):
    # When the feed cannot be reached, the last known values are shown.
    with mock.patch("urllib.request.urlopen", side_effect=OSError("down")):
        body = client.get("/").content.decode().replace(" ", " ")
    assert "11 553" in body
    assert "198 430" in body
    assert "5 310" in body
    # The height reporter, without which the iframe embed cannot size itself.
    assert "/static/accueil/js/resize-reporter.js" in body


def test_analytics_is_not_deferred(client):
    # Modules are implicitly deferred, so switching the page scripts to
    # type="module" must not drag the tag manager along: the container has to
    # boot before the page builds, or visits are under-counted.
    head = client.get("/").content.decode().split("</head>")[0]
    (tag,) = [line for line in head.splitlines() if "js/matomo.js" in line]
    assert "defer" not in tag
    assert "async" not in tag
    assert "module" not in tag


def test_index_loads_analytics(client):
    # Must be in the <head>: the tag manager has to boot before the page
    # builds, so a tag that drifted into the <body> would under-measure.
    head = client.get("/").content.decode().split("</head>")[0]
    assert "/static/accueil/js/matomo.js" in head


def test_index_inlines_svg_sprite(client):
    # The sprite is inlined and referenced by bare fragment: an external
    # reference (file#id) is blocked in a sandboxed iframe without
    # allow-same-origin, where the origin is opaque.
    body = client.get("/").content.decode()
    assert '<symbol viewBox="0 0 24 24" id="ri-user-add-line">' in body
    assert 'href="#ri-user-add-line"' in body
    assert "icones.svg" not in body


def test_index_allows_iframe_embedding(client):
    response = client.get("/")
    assert "X-Frame-Options" not in response.headers
    csp = response.headers["Content-Security-Policy"]
    assert "frame-ancestors" in csp
    assert "https://*.inclusion.gouv.fr" in csp
    assert "https://*.inclusion.beta.gouv.fr" in csp
    assert "https://*.cleverapps.io" in csp
    assert "https://*.scalingo.io" in csp
    # A site served from the developer machine may embed the deployed page.
    assert "http://localhost:*" in csp
    assert "127.0.0.1" not in csp  # DEBUG=False in tests


def test_index_has_no_inline_styles_or_scripts(client):
    response = client.get("/")
    body = response.content.decode()
    assert "style=" not in body
    assert "<style" not in body
    assert "<script>" not in body  # external scripts (src=…) only


def test_static_assets_are_served(client):
    for path in (
        "/static/accueil/js/iframe-embed.js",
        "/static/accueil/js/matomo.js",
        "/static/accueil/js/profiles.js",
        "/static/accueil/css/main.css",
        "/static/accueil/fonts/Marianne-Regular.woff2",
    ):
        assert client.get(path).status_code == 200, path
