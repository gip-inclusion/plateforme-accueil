def test_index_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    contenu = response.content.decode()
    assert "<title>Plateforme de l'inclusion</title>" in contenu
    assert "Un parcours adapté à chaque profil" in contenu
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
