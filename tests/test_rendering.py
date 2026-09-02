import io
import json
import pathlib
import re
from unittest import mock

import pytest
from django.conf import settings
from django.utils.html import escape

from accueil.sections.hero import Hero


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
    # The shipped list stays closed: a developer machine is opened per
    # deployment through CSP_EXTRA_FRAME_ANCESTORS, never in the code.
    assert "localhost" not in csp
    assert "127.0.0.1" not in csp


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
        "/static/accueil/js/analytics.js",
        "/static/accueil/css/main.css",
        "/static/accueil/fonts/Marianne-Regular.woff2",
    ):
        assert client.get(path).status_code == 200, path


def test_index_tags_the_sections_for_analytics(client):
    # Every interactive element of a section carries the pair the tag manager
    # reads; without it the click is invisible to the audience measurement.
    body = client.get("/").content.decode()
    assert "/static/accueil/js/analytics.js" in body
    for category in ["hero", "emplois", "services", "accompagnateurs", "pour-qui"]:
        assert f'data-matomo-category="{category}"' in body
    for action in ["onglet", "recherche", "raccourci", "carte", "voir-tout", "inscription"]:
        assert f'data-matomo-action="{action}"' in body


def test_analytics_tags_always_come_in_pairs(client):
    # A category without an action (or the other way round) is never measured:
    # the script keys off both attributes at once.
    body = client.get("/").content.decode()
    for tag in re.findall(r"<(?:a|button|form)[^>]*data-matomo-[^>]*>", body):
        assert "data-matomo-category=" in tag and "data-matomo-action=" in tag, tag


def test_an_extra_frame_ancestor_can_be_opened_per_deployment(client, settings):
    # The documented way to embed the deployed page from a developer machine.
    settings.SECURE_CSP = {"frame-ancestors": ["https://*.inclusion.gouv.fr", "http://localhost:8000"]}
    assert "http://localhost:8000" in client.get("/").headers["Content-Security-Policy"]


def test_the_documented_sandbox_allows_what_the_page_needs(client):
    # Hosts copy this snippet verbatim, and a token it omits disables the
    # feature it gates with no error anywhere.
    readme = pathlib.Path("README.md").read_text()
    sandbox = re.search(r'sandbox="([^"]+)"', readme).group(1).split()

    page = client.get("/").content.decode()
    if "<form" in page:
        assert "allow-forms" in sandbox
    if 'target="_top"' in page:
        assert "allow-top-navigation-by-user-activation" in sandbox
    # Together, these two let the framed page remove its own sandbox.
    assert not ("allow-same-origin" in sandbox and "allow-scripts" in sandbox)


def test_the_analytics_bridge_loads_before_the_page_is_measured(client):
    # The bridge holds the consent and the visitor id the tag needs, so it must
    # be listening before the container can fire.
    head = re.findall(r"<head>.*?</head>", client.get("/").content.decode(), re.DOTALL)[0]
    bridge = head.index("js/analytics-bridge.js")
    assert head.index("js/matomo.js") < bridge
    assert "defer" not in head[head.rindex("<script", 0, bridge) : bridge]


PROD = settings.PLATFORM_DEFAULT_ORIGIN
EMPLOI = PROD + Hero.searches["emploi"].results_path
INSERTION = PROD + Hero.searches["insertion"].results_path
ACCOMPAGNATEUR = PROD + Hero.searches["accompagnateur"].results_path


HOMONYMS = {
    "results": [
        {"id": "saint-denis-93", "text": "Saint-Denis (93)"},
        {"id": "saint-denis-974", "text": "Saint-Denis (974)"},
    ]
}


CITIES = {
    "results": [
        {"id": "lyon-69", "text": "Lyon (69)"},
        {"id": "lyon-la-foret-27", "text": "Lyons-la-Forêt (27)"},
    ]
}


def _homonyms(*args, **kwargs):
    return io.BytesIO(json.dumps(HOMONYMS).encode())


def _cities(*args, **kwargs):
    return io.BytesIO(json.dumps(CITIES).encode())


def test_hero_offers_the_three_search_types_without_js(client):
    body = client.get("/").content.decode()
    assert body.count('role="search"') == 1

    # `input:checked + label` styles the selected tab, so the adjacency is
    # load-bearing: without it nothing shows which search is about to run.
    radios = re.findall(r'<input class="recherche__onglet-radio"[^>]*>\s*<label class="recherche__onglet"[^>]*>', body)
    assert len(radios) == 3
    assert [re.search(r'value="([^"]+)"', r).group(1) for r in radios] == ["emploi", "insertion", "accompagnateur"]
    assert [r for r in radios if "checked" in r] == radios[:1]

    assert 'name="category"' in body
    assert body.count('name="city"') == 1


def test_search_dispatches_each_type_to_its_own_search_page(client):
    assert client.get("/search", {"type": "emploi"}).url == EMPLOI
    assert client.get("/search", {"type": "insertion"}).url == INSERTION
    assert client.get("/search", {"type": "accompagnateur"}).url == ACCOMPAGNATEUR


def test_search_carries_the_city_over(client):
    assert client.get("/search", {"type": "emploi", "city": "lyon-69"}).url == f"{EMPLOI}?city=lyon-69"


def test_search_drops_a_blank_city(client):
    # An empty parameter would filter on nothing; without it the results page
    # renders its own search form.
    assert client.get("/search", {"type": "emploi", "city": ""}).url == EMPLOI


def test_search_forwards_the_category_only_for_insertion(client):
    assert client.get("/search", {"type": "insertion", "category": "mobilite"}).url == f"{INSERTION}?category=mobilite"
    assert client.get("/search", {"type": "emploi", "category": "mobilite"}).url == EMPLOI


def test_search_combines_city_and_category_for_insertion(client):
    url = client.get("/search", {"type": "insertion", "city": "lyon-69", "category": "mobilite"}).url
    assert url.startswith(f"{INSERTION}?")
    assert "city=lyon-69" in url
    assert "category=mobilite" in url


@pytest.mark.parametrize(
    "asked",
    ["", "unknown", "https://evil.example", "//evil.example", "javascript:alert(1)", "../../../etc/passwd"],
)
def test_an_unusable_type_falls_back_to_the_default_search(client, asked):
    # "type" is only ever a key into Hero.searches: a crafted value that reached
    # the redirect target would be an open redirect.
    assert client.get("/search", {"type": asked}).url == EMPLOI
    assert client.get("/search").url == EMPLOI


@pytest.mark.parametrize("asked", ["insertion", "accompagnateur", "emploi"])
def test_a_link_can_land_on_one_search_type(client, asked):
    # Same "type" the form submits, resolved server-side so it works with no
    # JavaScript.
    body = client.get(f"/?type={asked}").content.decode()
    assert re.findall(r'value="([^"]+)"[^>]*checked', body) == [asked]


@pytest.mark.parametrize("asked", ["", "unknown", "https://evil.example", "../../etc"])
def test_an_unusable_type_still_checks_a_tab(client, asked):
    # No tab checked would submit an empty type and show no selected search.
    body = client.get(f"/?type={asked}").content.decode()
    assert re.findall(r'value="([^"]+)"[^>]*checked', body) == ["emploi"]


def test_a_typed_city_is_resolved_server_side(client):
    # The slug only ever comes from the autocomplete, so with no JavaScript a
    # required city would make the search impossible rather than degraded.
    with mock.patch("urllib.request.urlopen", side_effect=_cities):
        response = client.get("/search", {"type": "insertion", "city_name": "Lyon"})
    assert response.url == f"{INSERTION}?city=lyon-69"


def test_the_resolved_slug_wins_over_the_typed_name(client):
    # The visible text may have been edited after the pick; the slug is what
    # was actually chosen.
    with mock.patch("urllib.request.urlopen", side_effect=_cities):
        response = client.get("/search", {"type": "emploi", "city": "paris-75", "city_name": "Lyon"})
    assert response.url == f"{EMPLOI}?city=paris-75"


def test_an_unresolvable_city_name_still_reaches_the_results_page(client):
    assert client.get("/search", {"type": "emploi", "city_name": "Zzzz"}).url == EMPLOI


def test_an_inexact_city_name_is_not_resolved_for_the_visitor(client):
    # Upstream ranks by relevance: its top hit for "Lyo" would be a near miss
    # dressed as an answer.
    with mock.patch("urllib.request.urlopen", side_effect=_cities):
        assert client.get("/search", {"type": "emploi", "city_name": "Lyo"}).url == EMPLOI


def test_a_name_shared_by_several_cities_is_not_decided_for_the_visitor(client):
    # "Saint-Denis" is exactly right for both the 93 and the 974: an exact match
    # is not enough, it has to be unique.
    with mock.patch("urllib.request.urlopen", side_effect=_homonyms):
        assert client.get("/search", {"type": "emploi", "city_name": "Saint-Denis"}).url == EMPLOI


def test_an_accented_or_hyphenated_spelling_still_resolves(client):
    # "Lyons-la-Forêt" and "lyons la foret" are the same city.
    with mock.patch("urllib.request.urlopen", side_effect=_cities):
        response = client.get("/search", {"type": "emploi", "city_name": "lyons la foret"})
    assert response.url == f"{EMPLOI}?city=lyon-la-foret-27"


def test_the_city_field_is_required_and_carries_a_name(client):
    # `required` on a hidden input is ignored, and without a name the typed
    # value never reaches the server.
    body = client.get("/").content.decode()
    visible = re.search(r'<input class="champ__saisie"[^>]*>', body).group(0)
    assert 'name="city_name"' in visible
    assert "required" in visible


def test_no_template_comment_leaks_into_a_rendered_page():
    # Django only recognises `{# … #}` on a single line; spanning several prints
    # the comment into the page.
    offenders = []
    for template in pathlib.Path("accueil/templates").rglob("*.html"):
        text = template.read_text()
        for start in re.finditer(r"\{#", text):
            end = text.find("#}", start.start())
            if end == -1 or "\n" in text[start.start() : end]:
                offenders.append(f"{template}:{text[: start.start()].count(chr(10)) + 1}")
    assert offenders == []
