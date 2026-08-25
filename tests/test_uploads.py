"""Téléversement d'images : traitement, nommage, stockage."""

import importlib
import io
import logging

import pytest
from django import forms as django_forms
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.urls import clear_url_caches
from PIL import Image

import config.settings
import config.urls
from accueil import uploads
from accueil.forms import IllustrationEditor
from accueil.sections.base import Illustration
from accueil.templatetags.illustrations import illustration


ENV_KEYS = [
    "AWS_STORAGE_BUCKET_NAME",
    "AWS_S3_ENDPOINT_URL",
    "AWS_S3_REGION_NAME",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "LOCAL_UPLOADS_ENABLED",
    "DEBUG",
]

COMPLETE_BUCKET = {
    "AWS_STORAGE_BUCKET_NAME": "some-bucket",
    "AWS_S3_ENDPOINT_URL": "https://s3.example.invalid",
    "AWS_S3_REGION_NAME": "some-region",
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
    ("bucket_complete", "local_opt_in", "debug", "expected"),
    [
        (True, False, False, True),  # bucket seul suffit
        (True, True, False, True),  # les deux : toujours activé
        (False, True, False, True),  # opt-in local seul, sans bucket
        (False, False, False, False),  # ni bucket complet, ni opt-in : pas d'upload
        (False, False, True, False),  # DEBUG seul ne doit JAMAIS suffire (régression du "or DEBUG")
    ],
)
def test_uploads_enabled_truth_table(reload_settings, bucket_complete, local_opt_in, debug, expected):
    env = dict(COMPLETE_BUCKET) if bucket_complete else {}
    if local_opt_in:
        env["LOCAL_UPLOADS_ENABLED"] = "1"
    if debug:
        env["DEBUG"] = "1"
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


def a_file(width, height, name="photo.png", colour=(120, 90, 60)):
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), colour).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def a_transparent_file(width, height, name="pictogram.png"):
    # Un pictogramme typique : fond transparent, un coin repérable pour
    # vérifier que le canal alpha survit au traitement.
    buffer = io.BytesIO()
    image = Image.new("RGBA", (width, height), (10, 20, 30, 255))
    image.putpixel((0, 0), (0, 0, 0, 0))
    image.save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def stored(tmp_path, settings, uploaded, **kwargs):
    settings.MEDIA_ROOT = tmp_path
    key = uploads.store(uploaded, **kwargs)
    return key, Image.open(tmp_path / key)


def test_a_large_image_is_narrowed_and_converted(tmp_path, settings):
    key, image = stored(tmp_path, settings, a_file(2400, 1500), max_width=800, ratio=(16, 10))
    assert key.startswith("uploads/") and key.endswith(".webp")
    assert image.format == "WEBP"
    assert image.size == (800, 500)


def test_a_small_image_is_never_enlarged(tmp_path, settings):
    _, image = stored(tmp_path, settings, a_file(320, 200), max_width=800, ratio=(16, 10))
    assert image.size == (320, 200)


def test_a_wrong_shape_is_cropped_to_the_declared_ratio(tmp_path, settings):
    # Le gabarit code width=122 height=86 : une image carrée doit en ressortir
    # au bon format, sinon l'attribut ment et la page saute.
    _, image = stored(tmp_path, settings, a_file(1000, 1000), max_width=366, ratio=(122, 86))
    assert image.size == (366, 258)


def test_without_a_ratio_the_shape_is_kept(tmp_path, settings):
    _, image = stored(tmp_path, settings, a_file(1000, 400), max_width=500)
    assert image.size == (500, 200)


def test_the_same_file_twice_gives_the_same_key(tmp_path, settings):
    first, _ = stored(tmp_path, settings, a_file(400, 250), max_width=400, ratio=(16, 10))
    second, _ = stored(tmp_path, settings, a_file(400, 250), max_width=400, ratio=(16, 10))
    assert first == second


def test_something_that_is_not_an_image_is_refused(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    not_an_image = SimpleUploadedFile("cv.pdf", b"%PDF-1.4 not an image", content_type="application/pdf")
    with pytest.raises(ValidationError):
        uploads.store(not_an_image, max_width=800)


def test_an_oversized_file_is_refused(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    heavy = SimpleUploadedFile("huge.png", b"x" * (uploads.MAX_BYTES + 1), content_type="image/png")
    with pytest.raises(ValidationError):
        uploads.store(heavy, max_width=800)


def test_a_transparent_pictogram_keeps_its_alpha_channel(tmp_path, settings):
    # Trois des quatre illustrations déclarées sont des WebP susceptibles
    # d'avoir un fond transparent (pictogrammes) : les aplatir sur un noir
    # implicite serait faux.
    _, image = stored(tmp_path, settings, a_transparent_file(200, 200), max_width=200)
    assert image.mode == "RGBA"
    assert image.getpixel((0, 0))[3] == 0


def test_a_huge_pixel_count_is_refused_before_decoding(tmp_path, settings, monkeypatch):
    # Une taille compressée modeste peut encore déclarer des dimensions
    # énormes : le refus doit se faire sur les dimensions déclarées, avant
    # même d'appeler `.load()` — on épingle l'ordre, pas seulement le refus.
    settings.MEDIA_ROOT = tmp_path
    bomb = a_file(9000, 9000)  # 81 mégapixels, au-delà de MAX_PIXELS

    def boom(self, *args, **kwargs):
        raise AssertionError("image.load() ne doit pas être appelé sur une image trop grande")

    monkeypatch.setattr(Image.Image, "load", boom)
    with pytest.raises(ValidationError, match="pixels"):
        uploads.store(bomb, max_width=800)


def test_a_sliver_source_does_not_round_a_dimension_to_zero(tmp_path, settings):
    # 2000x1 avec max_width=800 : round(1 * 800/2000) == round(0.4) == 0 sans
    # le clamp — de quoi faire planter `ImageOps.fit` avec une division par
    # zéro.
    _, image = stored(tmp_path, settings, a_file(2000, 1), max_width=800)
    assert image.size == (800, 1)


def test_an_extreme_ratio_is_clamped_both_ways(tmp_path, settings):
    # Une source 1x1 face à un ratio très large ou très haut arrondit une
    # dimension à 0 des deux côtés de la branche `ratio` sans le clamp.
    _, wide = stored(tmp_path, settings, a_file(1, 1), max_width=100, ratio=(32, 1))
    assert wide.size == (1, 1)

    _, tall = stored(tmp_path, settings, a_file(1, 1), max_width=100, ratio=(1, 32))
    assert tall.size == (1, 1)


def test_a_source_exactly_at_max_width_is_unchanged(tmp_path, settings):
    _, image = stored(tmp_path, settings, a_file(500, 300), max_width=500)
    assert image.size == (500, 300)


def test_pillows_own_bomb_guard_is_an_expected_refusal(tmp_path, settings, caplog):
    # Pillow lève `DecompressionBombError` au-delà de ~178 Mpx, depuis
    # `Image.open` — donc avant notre propre contrôle. Cette exception dérive
    # d'`Exception` et non d'`OSError` : sans mention explicite elle tombait
    # dans la branche « erreur inattendue », annonçant à la rédactrice un
    # fichier illisible (il ne l'est pas, il est énorme) et journalisant en
    # ERROR un refus parfaitement attendu.
    settings.MEDIA_ROOT = tmp_path
    buffer = io.BytesIO()
    Image.new("L", (20000, 20000)).save(buffer, format="PNG")
    enormous = SimpleUploadedFile("bombe.png", buffer.getvalue(), content_type="image/png")

    with caplog.at_level(logging.ERROR, logger="accueil.uploads"):
        with pytest.raises(ValidationError, match="pixels"):
            uploads.store(enormous, max_width=800)
    assert caplog.records == []


def an_editor(**kwargs):
    return IllustrationEditor(
        Illustration(label="Visuel", max_width=800, ratio=(16, 10), initial="accueil/img/hero.webp"),
        **kwargs,
    )


class Upload(django_forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["visual"] = an_editor()


def test_posting_no_file_keeps_the_current_value():
    form = Upload(data={"visual_current": "accueil/img/hero.webp"}, files={})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["visual"] == "accueil/img/hero.webp"


def test_posting_a_file_stores_it_and_yields_a_key(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    form = Upload(data={"visual_current": "accueil/img/hero.webp"}, files={"visual": a_file(1600, 1000)})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["visual"].startswith("uploads/")


def test_a_bad_file_is_reported_on_the_field(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    bad = SimpleUploadedFile("cv.pdf", b"%PDF-1.4", content_type="application/pdf")
    form = Upload(data={"visual_current": "accueil/img/hero.webp"}, files={"visual": bad})
    assert not form.is_valid()
    assert "visual" in form.errors


@override_settings(UPLOADS_ENABLED=False)
def test_without_durable_storage_the_field_offers_no_upload():
    rendered = Upload(initial={"visual": "accueil/img/hero.webp"}).as_p()
    assert 'type="file"' not in rendered
    assert "accueil/img/hero.webp" in rendered
