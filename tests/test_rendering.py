import io
import json
from unittest import mock


def test_index_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    contenu = response.content.decode()
    assert "<title>Plateforme de l'inclusion</title>" in contenu
    assert "Un parcours adapté à chaque profil" in contenu


def test_stats_affichent_le_flux(client):
    # Numbers come from the (mocked) key-figures feed, formatted for French.
    contenu = client.get("/").content.decode().replace(" ", " ")
    assert "12 345" in contenu  # offres_ouvertes
    assert "200 000" in contenu  # services_di
    assert "6 000" in contenu  # prescripteurs_actifs


def test_villes_proxy_mappe_slug_et_label(client):
    feed = {
        "results": [
            {"text": "Lyon (69)", "id": "lyon-69"},
            {"text": "Lyon 1er (69)", "id": "lyon-1er-69"},
        ]
    }
    with mock.patch(
        "accueil.views.urllib.request.urlopen",
        side_effect=lambda *a, **k: io.BytesIO(json.dumps(feed).encode()),
    ):
        data = client.get("/api/villes?q=lyon").json()
    assert data["resultats"][0] == {"slug": "lyon-69", "label": "Lyon (69)"}
    assert len(data["resultats"]) == 2


def test_villes_requete_vide(client):
    # No query -> no upstream call, empty list.
    assert client.get("/api/villes").json() == {"resultats": []}


def test_hero_cible_les_trois_recherches(client):
    contenu = client.get("/").content.decode()
    assert "emplois.inclusion.beta.gouv.fr/search/employers" in contenu
    assert "emplois.inclusion.beta.gouv.fr/search/prescribers" in contenu
    assert "emplois.inclusion.beta.gouv.fr/search/services" in contenu
    assert 'name="category"' in contenu  # services thematic select
    assert 'value="creer-une-entreprise"' in contenu


def test_stats_repli_si_flux_indisponible(client):
    # When the feed cannot be reached, the last known values are shown.
    with mock.patch("accueil.views.urllib.request.urlopen", side_effect=OSError("down")):
        contenu = client.get("/").content.decode().replace(" ", " ")
    assert "11 553" in contenu
    assert "198 430" in contenu
    assert "5 310" in contenu
    # The height reporter, without which the iframe embed cannot size itself.
    assert "/static/accueil/js/resize-reporter.js" in contenu


def test_index_loads_analytics(client):
    # Must be in the <head>: the tag manager has to boot before the page
    # builds, so a tag that drifted into the <body> would under-measure.
    entete = client.get("/").content.decode().split("</head>")[0]
    assert "/static/accueil/js/matomo.js" in entete


def test_index_inlines_svg_sprite(client):
    # The sprite is inlined and referenced by bare fragment: an external
    # reference (file#id) is blocked in a sandboxed iframe without
    # allow-same-origin, where the origin is opaque.
    contenu = client.get("/").content.decode()
    assert '<symbol viewBox="0 0 24 24" id="ri-user-add-line">' in contenu
    assert 'href="#ri-user-add-line"' in contenu
    assert "icones.svg" not in contenu


def test_index_allows_iframe_embedding(client):
    response = client.get("/")
    assert "X-Frame-Options" not in response.headers
    csp = response.headers["Content-Security-Policy"]
    assert "frame-ancestors" in csp
    assert "https://*.inclusion.gouv.fr" in csp
    assert "https://*.inclusion.beta.gouv.fr" in csp
    assert "https://*.cleverapps.io" in csp
    assert "https://*.scalingo.io" in csp
    assert "localhost" not in csp  # DEBUG=False in tests


def test_index_has_no_inline_styles_or_scripts(client):
    response = client.get("/")
    contenu = response.content.decode()
    assert "style=" not in contenu
    assert "<style" not in contenu
    assert "<script>" not in contenu  # external scripts (src=…) only


def test_static_assets_are_served(client):
    for chemin in (
        "/static/accueil/js/iframe-embed.js",
        "/static/accueil/js/matomo.js",
        "/static/accueil/js/profils.js",
        "/static/accueil/css/main.css",
        "/static/accueil/fonts/Marianne-Regular.woff2",
    ):
        assert client.get(chemin).status_code == 200, chemin
