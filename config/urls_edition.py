from django.urls import path

from accueil import editing


app_name = "edition"

urlpatterns = [
    path("", editing.plan, name="plan"),
    path("section/<int:pk>/deplacer", editing.move, name="move"),
    path("section/<int:pk>/afficher", editing.toggle, name="toggle"),
]
