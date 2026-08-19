import os
import urllib.parse
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-dev-only")

DEBUG = os.environ.get("DEBUG", "") == "1"

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")

# The admin is the stopgap editing UI, until /pilotage/ and Authentik land.
# Only its URLs are gated, so a deploy never exposes a login form backed by
# local passwords. The apps stay installed in every environment: making
# INSTALLED_APPS conditional would make the set of migrations depend on the
# environment, which is a good way to lose a table.
ADMIN_ENABLED = os.environ.get("ADMIN_ENABLED", "1" if DEBUG else "") == "1"

# Authentik (OpenID Connect). Off until a client is configured: no endpoint is
# hard-coded here, the whole configuration comes from the environment.
OIDC_RP_CLIENT_ID = os.environ.get("OIDC_RP_CLIENT_ID", "")
OIDC_RP_CLIENT_SECRET = os.environ.get("OIDC_RP_CLIENT_SECRET", "")
OIDC_PROVIDER_URL = os.environ.get("OIDC_PROVIDER_URL", "").rstrip("/")
OIDC_ENABLED = bool(OIDC_RP_CLIENT_ID and OIDC_RP_CLIENT_SECRET and OIDC_PROVIDER_URL)

# Authentik group names. Membership of the first opens the editing UI, of the
# second the Publier button.
OIDC_EDITOR_GROUP = os.environ.get("OIDC_EDITOR_GROUP", "accueil-redaction")
OIDC_PUBLISHER_GROUP = os.environ.get("OIDC_PUBLISHER_GROUP", "accueil-publication")

if OIDC_ENABLED:
    AUTHENTICATION_BACKENDS = ["accueil.auth.AuthentikBackend"]
    OIDC_RP_SIGN_ALGO = "RS256"
    OIDC_RP_SCOPES = "openid email profile"
    OIDC_OP_AUTHORIZATION_ENDPOINT = f"{OIDC_PROVIDER_URL}/authorize/"
    OIDC_OP_TOKEN_ENDPOINT = f"{OIDC_PROVIDER_URL}/token/"
    OIDC_OP_USER_ENDPOINT = f"{OIDC_PROVIDER_URL}/userinfo/"
    OIDC_OP_JWKS_ENDPOINT = f"{OIDC_PROVIDER_URL}/jwks/"
    OIDC_USE_PKCE = True
    # Re-checks the session against Authentik rather than trusting a cookie for
    # the full two weeks: without it, revoking an editor upstream would not bite
    # until their session expired.
    OIDC_RENEW_ID_TOKEN_EXPIRY_SECONDS = 15 * 60
    LOGIN_URL = "oidc_authentication_init"
    LOGIN_REDIRECT_URL = "/edition/"
    LOGOUT_REDIRECT_URL = "/edition/"
else:
    LOGIN_URL = "admin:login"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "accueil",
]
if OIDC_ENABLED:
    INSTALLED_APPS += ["mozilla_django_oidc"]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    # Needed by the admin. None of them sets a cookie on the public page,
    # which has no form that posts — there is a test pinning that down.
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]
if OIDC_ENABLED:
    MIDDLEWARE += ["mozilla_django_oidc.middleware.SessionRefresh"]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
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
