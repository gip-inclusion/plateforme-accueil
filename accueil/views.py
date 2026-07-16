from functools import cache

from django.conf import settings
from django.http import HttpResponse


@cache
def _maquette() -> bytes:
    chemin = settings.BASE_DIR / "accueil" / "static" / "accueil" / "exemple-francois.html"
    return chemin.read_bytes()


def index(request):
    # La maquette est un document HTML autonome : on la sert telle quelle (sans
    # moteur de template) tout en passant par les middlewares, notamment la CSP
    # frame-ancestors qui autorise l'embarquement en iframe sur les sites hôtes.
    return HttpResponse(_maquette())
