import json
import urllib.parse
import urllib.request

from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render


# Public open-data feed backing the "key figures" band.
CHIFFRES_URL = "https://statistiques.inclusion.gouv.fr/dashboards/chiffres-cles-plateforme/data.json"
CHIFFRES_CACHE_KEY = "chiffres_cles"
CHIFFRES_CACHE_TTL = 3600  # seconds

# Indicator id -> fallback value, used when the feed is unreachable. The keys
# also decide which indicators are shown, and in which order.
CHIFFRES_DEFAUT = {
    "offres_ouvertes": 11553,
    "services_di": 198430,
    "prescripteurs_actifs": 5310,
}

# City autocomplete proxied from "les emplois de l'inclusion". The same endpoint
# backs the employer and prescriber searches; it is proxied server-side because
# it sends no CORS headers, so the embedded page cannot call it directly.
VILLES_URL = "https://emplois.inclusion.beta.gouv.fr/autocomplete/cities"
VILLES_CACHE_TTL = 300  # seconds
VILLES_MAX = 8


def _format_fr(nombre):
    # French thousands separator: a non-breaking space (e.g. 11 553).
    return f"{nombre:,}".replace(",", " ")


def _chiffres_cles():
    # Fetched once per TTL and cached. Falls back to the last known values so
    # the page always renders, even if the feed is slow or unavailable.
    valeurs = cache.get(CHIFFRES_CACHE_KEY)
    if valeurs is not None:
        return valeurs

    nombres = dict(CHIFFRES_DEFAUT)
    try:
        with urllib.request.urlopen(CHIFFRES_URL, timeout=5) as reponse:
            data = json.load(reponse)
        indicateurs = data.get("indicators", []) if isinstance(data, dict) else []
        par_id = {
            item["id"]: item["value"]
            for item in indicateurs
            if isinstance(item, dict) and "id" in item and "value" in item
        }
        for cle in CHIFFRES_DEFAUT:
            if isinstance(par_id.get(cle), int):
                nombres[cle] = par_id[cle]
    except Exception:
        pass  # any failure -> keep fallback values so the page always renders

    valeurs = {cle: _format_fr(nombres[cle]) for cle in CHIFFRES_DEFAUT}
    cache.set(CHIFFRES_CACHE_KEY, valeurs, CHIFFRES_CACHE_TTL)
    return valeurs


def index(request):
    return render(request, "accueil/index.html", {"chiffres": _chiffres_cles()})


def villes(request):
    # City suggestions for the hero search, resolved to the slug that the
    # employer and prescriber result pages expect (e.g. "lyon-69").
    terme = request.GET.get("q", "").strip()
    if not terme:
        return JsonResponse({"resultats": []})

    cle = f"villes:{terme.lower()}"
    resultats = cache.get(cle)
    if resultats is None:
        resultats = []
        url = f"{VILLES_URL}?slug=&term={urllib.parse.quote(terme)}"
        try:
            with urllib.request.urlopen(url, timeout=5) as reponse:
                data = json.load(reponse)
            for item in data.get("results", [])[:VILLES_MAX]:
                if isinstance(item, dict) and item.get("id") and item.get("text"):
                    resultats.append({"slug": item["id"], "label": item["text"]})
        except Exception:
            resultats = []
        cache.set(cle, resultats, VILLES_CACHE_TTL)

    return JsonResponse({"resultats": resultats})
