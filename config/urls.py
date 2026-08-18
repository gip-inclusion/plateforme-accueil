from django.conf import settings
from django.urls import path

from accueil import views


urlpatterns = [
    path("", views.index, name="index"),
    path("api/cities", views.cities, name="cities"),
]

if settings.ADMIN_ENABLED:
    from django.contrib import admin

    urlpatterns += [path("admin/", admin.site.urls)]
