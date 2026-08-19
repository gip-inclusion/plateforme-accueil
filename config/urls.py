from django.conf import settings
from django.urls import include, path

from accueil import views


urlpatterns = [
    path("", views.index, name="index"),
    path("api/cities", views.cities, name="cities"),
    path("edition/", include("config.urls_edition")),
]

if settings.OIDC_ENABLED:
    urlpatterns += [path("oidc/", include("mozilla_django_oidc.urls"))]

if settings.ADMIN_ENABLED or settings.OIDC_ENABLED:
    from django.contrib import admin

    urlpatterns += [path("admin/", admin.site.urls)]
