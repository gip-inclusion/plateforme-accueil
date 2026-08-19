from django.conf import settings
from django.urls import include, path

from accueil import views


urlpatterns = [
    path("", views.index, name="index"),
    path("api/cities", views.cities, name="cities"),
]

if settings.OIDC_ENABLED:
    urlpatterns += [path("oidc/", include("mozilla_django_oidc.urls"))]

# The editing UI and the admin are only routable when there is a way to sign in.
# Mounting the editor without one gave a 500 rather than a login: the redirect
# had nowhere to point.
if settings.ADMIN_ENABLED or settings.OIDC_ENABLED:
    from django.contrib import admin

    urlpatterns += [
        path("edition/", include("config.urls_edition")),
        path("admin/", admin.site.urls),
    ]
