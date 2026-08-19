"""The production URLconf as it stands by default: no admin, no OIDC.

Used to pin that /edition/ still redirects to a login rather than blowing up on
a missing `admin:login` route.
"""

from django.urls import include, path

from accueil import views


urlpatterns = [
    path("", views.index, name="index"),
    path("edition/", include("config.urls_edition")),
]
