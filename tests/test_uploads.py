"""Téléversement d'images : traitement, nommage, stockage."""

import importlib

import pytest
from django.test import Client, override_settings
from django.urls import clear_url_caches

import config.settings
import config.urls
from accueil.templatetags.illustrations import illustration


ENV_KEYS = [
    "AWS_STORAGE_BUCKET_NAME",
    "AWS_S3_ENDPOINT_URL",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "LOCAL_UPLOADS_ENABLED",
]

COMPLETE_BUCKET = {
    "AWS_STORAGE_BUCKET_NAME": "some-bucket",
    "AWS_S3_ENDPOINT_URL": "https://s3.fr-par.scw.cloud",
    "AWS_ACCESS_KEY_ID": "key",
    "AWS_SECRET_ACCESS_KEY": "secret",
}


def _reload_settings(monkeypatch, **env):
    # Même mécanique que les tests analogues sur DATABASE_URL/ADMIN_ENABLED
    # (tests/test_cms.py) : ces réglages se calculent à l'import du module,
    # donc on manipule l'environnement puis on recharge le module pour de
    # vrai, plutôt que de rejouer le calcul dans le test.
    for name in ENV_KEYS:
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return importlib.reload(config.settings)


@pytest.fixture
def reload_settings(monkeypatch):
    yield lambda **env: _reload_settings(monkeypatch, **env)
    importlib.reload(config.settings)  # remet le module dans l'état ambiant pour la suite


def test_a_complete_bucket_configuration_installs_s3_storage(reload_settings):
    reloaded = reload_settings(**COMPLETE_BUCKET)
    assert reloaded.S3_CONFIGURED is True
    assert reloaded.STORAGES["default"]["BACKEND"] == "storages.backends.s3.S3Storage"
    assert reloaded.UPLOADS_ENABLED is True


def test_an_incomplete_bucket_configuration_disables_uploads_but_still_renders(reload_settings):
    # Le cas critique : un endpoint oublié ne doit ni empêcher le démarrage,
    # ni faire croire à un stockage durable.
    incomplete = dict(COMPLETE_BUCKET)
    del incomplete["AWS_S3_ENDPOINT_URL"]
    reloaded = reload_settings(**incomplete)

    assert reloaded.S3_CONFIGURED is False
    assert reloaded.STORAGES["default"]["BACKEND"] == "django.core.files.storage.FileSystemStorage"
    assert reloaded.UPLOADS_ENABLED is False

    # Et la page publique doit toujours répondre : c'est la régression que ce
    # test couvre, pas seulement un calcul de réglages.
    with override_settings(STORAGES=reloaded.STORAGES, UPLOADS_ENABLED=reloaded.UPLOADS_ENABLED):
        response = Client().get("/")
        assert response.status_code == 200


@override_settings(
    STORAGES={
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "bucket_name": "some-bucket",
                "endpoint_url": "https://unreachable.example.invalid",
                "access_key": "key",
                "secret_key": "secret",
                "querystring_auth": False,
            },
        }
    }
)
def test_illustration_composes_a_url_without_reaching_the_network():
    # Propriété que le commentaire `querystring_auth` protège : composer
    # l'URL est une opération purement locale, jamais un appel réseau ni une
    # exception — même contre un endpoint inaccessible.
    url = illustration("uploads/does-not-exist.webp")
    assert url.startswith("https://")


@pytest.mark.parametrize(
    ("bucket_complete", "local_opt_in", "expected"),
    [
        (True, False, True),  # bucket seul suffit
        (True, True, True),  # les deux : toujours activé
        (False, True, True),  # opt-in local seul, sans bucket
        (False, False, False),  # ni bucket complet, ni opt-in : pas d'upload
    ],
)
def test_uploads_enabled_truth_table(reload_settings, bucket_complete, local_opt_in, expected):
    env = dict(COMPLETE_BUCKET) if bucket_complete else {}
    if local_opt_in:
        env["LOCAL_UPLOADS_ENABLED"] = "1"
    reloaded = reload_settings(**env)
    assert reloaded.UPLOADS_ENABLED is expected


def test_a_locally_stored_upload_is_actually_served(tmp_path):
    # Sans cette route, un développeur en LOCAL_UPLOADS_ENABLED stocke un
    # fichier sur disque, obtient une URL plausible... et une image cassée :
    # rien ne servait MEDIA_ROOT avant ce test.
    upload = tmp_path / "uploads"
    upload.mkdir()
    (upload / "x.webp").write_bytes(b"fake-image-bytes")

    try:
        with override_settings(LOCAL_UPLOADS_ENABLED=True, MEDIA_URL="/media/", MEDIA_ROOT=tmp_path):
            importlib.reload(config.urls)
            clear_url_caches()
            response = Client().get("/media/uploads/x.webp")
            assert response.status_code == 200
            assert b"".join(response.streaming_content) == b"fake-image-bytes"
    finally:
        importlib.reload(config.urls)
        clear_url_caches()
