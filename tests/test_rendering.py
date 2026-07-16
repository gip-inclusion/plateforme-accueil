def test_index_serves_maquette(client):
    response = client.get("/")
    assert response.status_code == 200
    contenu = response.content.decode()
    # La page servie est la maquette autonome...
    assert "<title>Plateforme de l&#39;inclusion" in contenu
    # ...avec le script de report de hauteur injecté pour l'embarquement iframe.
    assert "/static/accueil/js/resize-reporter.js" in contenu


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


def test_iframe_embed_script_is_served(client):
    response = client.get("/static/accueil/js/iframe-embed.js")
    assert response.status_code == 200
