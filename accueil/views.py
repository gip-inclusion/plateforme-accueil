import json
import urllib.parse
import urllib.request

from django.contrib.auth import logout
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import redirect, render

from accueil import content


# City autocomplete proxied from "les emplois de l'inclusion". The same endpoint
# backs the employer and prescriber searches; it is proxied server-side because
# it sends no CORS headers, so the embedded page cannot call it directly.
CITIES_URL = "https://plateforme.inclusion.gouv.fr/autocomplete/cities"
CITIES_CACHE_TTL = 300  # seconds
CITIES_MAX = 8


def index(request):
    return render(
        request,
        "accueil/index.html",
        {"sections": content.page_sections()},
    )


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

    return JsonResponse(
        {"results": results},
        headers={"Access-Control-Allow-Origin": "*"},
    )


def logout_url(request):
    logout(request)
    return redirect("index")
