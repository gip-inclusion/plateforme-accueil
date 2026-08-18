import json
import urllib.parse
import urllib.request

from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render


# Public open-data feed backing the "key figures" band.
KEY_FIGURES_URL = "https://statistiques.inclusion.gouv.fr/dashboards/chiffres-cles-plateforme/data.json"
KEY_FIGURES_CACHE_KEY = "key_figures"
KEY_FIGURES_CACHE_TTL = 3600  # seconds

# Indicator id -> fallback value, used when the feed is unreachable. The keys
# also decide which indicators are shown, and in which order.
KEY_FIGURES_FALLBACK = {
    "offres_ouvertes": 11553,
    "services_di": 198430,
    "prescripteurs_actifs": 5310,
}

# City autocomplete proxied from "les emplois de l'inclusion". The same endpoint
# backs the employer and prescriber searches; it is proxied server-side because
# it sends no CORS headers, so the embedded page cannot call it directly.
CITIES_URL = "https://emplois.inclusion.beta.gouv.fr/autocomplete/cities"
CITIES_CACHE_TTL = 300  # seconds
CITIES_MAX = 8


def _format_french(number):
    # French thousands separator: a non-breaking space (e.g. 11 553).
    return f"{number:,}".replace(",", " ")


def _key_figures():
    # Fetched once per TTL and cached. Falls back to the last known values so
    # the page always renders, even if the feed is slow or unavailable.
    values = cache.get(KEY_FIGURES_CACHE_KEY)
    if values is not None:
        return values

    numbers = dict(KEY_FIGURES_FALLBACK)
    try:
        with urllib.request.urlopen(KEY_FIGURES_URL, timeout=5) as response:
            data = json.load(response)
        indicators = data.get("indicators", []) if isinstance(data, dict) else []
        by_id = {
            item["id"]: item["value"]
            for item in indicators
            if isinstance(item, dict) and "id" in item and "value" in item
        }
        for key in KEY_FIGURES_FALLBACK:
            if isinstance(by_id.get(key), int):
                numbers[key] = by_id[key]
    except Exception:
        pass  # any failure -> keep fallback values so the page always renders

    values = {key: _format_french(numbers[key]) for key in KEY_FIGURES_FALLBACK}
    cache.set(KEY_FIGURES_CACHE_KEY, values, KEY_FIGURES_CACHE_TTL)
    return values


def index(request):
    return render(request, "accueil/index.html", {"figures": _key_figures()})


def cities(request):
    # City suggestions for the hero search, resolved to the slug that the
    # employer and prescriber result pages expect (e.g. "lyon-69").
    term = request.GET.get("q", "").strip()
    if not term:
        return JsonResponse({"results": []})

    key = f"cities:{term.lower()}"
    results = cache.get(key)
    if results is None:
        results = []
        url = f"{CITIES_URL}?slug=&term={urllib.parse.quote(term)}"
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.load(response)
            for item in data.get("results", [])[:CITIES_MAX]:
                if isinstance(item, dict) and item.get("id") and item.get("text"):
                    results.append({"slug": item["id"], "label": item["text"]})
        except Exception:
            results = []
        cache.set(key, results, CITIES_CACHE_TTL)

    return JsonResponse({"results": results})
