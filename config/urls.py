from django.urls import path

from accueil import views


urlpatterns = [
    path("", views.index, name="index"),
    path("api/villes", views.villes, name="villes"),
]
