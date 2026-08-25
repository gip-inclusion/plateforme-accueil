"""Téléversement d'images : traitement, nommage, stockage."""

from django.conf import settings


def test_a_media_url_is_always_configured():
    # Le filtre `illustration` compose une URL sans jamais interroger le
    # stockage ; il lui faut donc une racine, bucket ou pas.
    assert settings.MEDIA_URL


def test_media_is_not_durable_without_a_bucket():
    # Sur un conteneur éphémère, le disque local disparaît au redéploiement :
    # sans bucket et hors DEBUG, l'interface doit refuser le téléversement
    # plutôt que perdre le travail d'un rédacteur en silence.
    assert settings.MEDIA_CONFIGURED == (bool(settings.AWS_STORAGE_BUCKET_NAME) or settings.DEBUG)
