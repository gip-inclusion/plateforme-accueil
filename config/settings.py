import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-dev-only")

DEBUG = os.environ.get("DEBUG", "") == "1"

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "accueil",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# The page is built to be embedded in an iframe: no X-Frame-Options, the
# allowed hosts are carried by the CSP instead.
SECURE_CSP = {
    "frame-ancestors": [
        "https://*.inclusion.gouv.fr",
        "https://*.inclusion.beta.gouv.fr",
        "https://*.cleverapps.io",
        "https://*.scalingo.io",
    ],
}

if DEBUG:
    SECURE_CSP["frame-ancestors"] += ["http://localhost:*", "http://127.0.0.1:*"]

# Extra origins allowed to embed the page (comma-separated), to test an embed
# from a host not listed above.
SECURE_CSP["frame-ancestors"] += [
    origin for origin in os.environ.get("CSP_EXTRA_FRAME_ANCESTORS", "").split(",") if origin
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Also serve statics located by the finders, which matters when collectstatic
# has not run (dev and tests); in production the manifest still wins.
WHITENOISE_USE_FINDERS = True

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
