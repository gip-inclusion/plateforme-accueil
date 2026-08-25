from django.urls import path

from accueil import editing


app_name = "edition"

urlpatterns = [
    path("", editing.plan, name="plan"),
    path("section/<int:pk>/", editing.section, name="section"),
    path("section/<int:pk>/deplacer", editing.move, name="move"),
    path("section/<int:pk>/afficher", editing.toggle, name="toggle"),
    path("section/<int:pk>/reinitialiser/<str:name>", editing.reset_field, name="reset-field"),
    path("section/<int:pk>/liste/<str:name>/<int:index>/dupliquer", editing.item_duplicate, name="item-duplicate"),
    path("section/<int:pk>/liste/<str:name>/<int:index>/supprimer", editing.item_delete, name="item-delete"),
    path("section/<int:pk>/liste/<str:name>/<int:index>/deplacer", editing.item_move, name="item-move"),
]
