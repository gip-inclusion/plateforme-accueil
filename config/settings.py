import os
import urllib.parse
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

# The database is optional. Without DATABASE_URL the page renders the defaults
# declared in `accueil/sections/`, exactly as it did before the CMS existed —
# which is also what happens if the database is configured but unreachable.
DB_SCHEMA = os.environ.get("DB_SCHEMA", "accueil")

DATABASES = {}
if _url := os.environ.get("DATABASE_URL", ""):
    _parts = urllib.parse.urlparse(_url)
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _parts.path.lstrip("/"),
        "USER": urllib.parse.unquote(_parts.username or ""),
        "PASSWORD": urllib.parse.unquote(_parts.password or ""),
        "HOST": _parts.hostname or "",
        "PORT": str(_parts.port or ""),
        "CONN_MAX_AGE": 60,
        # Everything lives in its own schema, so the project can share a cluster.
        "OPTIONS": {"options": f"-c search_path={DB_SCHEMA},public"},
    }

# Django swaps an empty DATABASES for a dummy backend as soon as the ORM is
# touched, so the question has to be answered while it still means something.
DATABASE_CONFIGURED = bool(DATABASES)

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
