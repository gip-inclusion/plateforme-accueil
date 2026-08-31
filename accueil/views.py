import json
import unicodedata
import urllib.parse
import urllib.request

from django.contrib.auth import logout
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import redirect, render

from accueil import content
from accueil.sections.hero import Hero


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
        {
            "sections": content.page_sections(),
            # `/?type=insertion` lands straight on one search. Resolved
            # server-side, so it works with no JavaScript.
            "selected_search": Hero.resolve_search(request.GET.get("type", "")),
        },
    )


def city_matches(term):
    """Cities matching a free-text term, each with the slug the result pages
    expect (e.g. "lyon-69"). Shared by the autocomplete endpoint and by the
    server-side resolution, so the two cannot disagree about what a name means.
    """
    term = term.strip()
    if not term:
        return []

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
            # Not cached: an unreachable upstream self-heals.
            return []
        cache.set(key, results, CITIES_CACHE_TTL)

    return results


def cities(request):
    return JsonResponse(
        {"results": city_matches(request.GET.get("q", ""))},
        headers={"Access-Control-Allow-Origin": "*"},
    )


def login_view(request):
    return redirect("oidc_authentication_init")


def logout_url(request):
    # It would be better to logout from our sso but's it's not really an issue
    logout(request)
    return redirect("index")


def _normalised(name):
    """A city name reduced to what makes two spellings the same one."""
    folded = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return " ".join(folded.replace("-", " ").lower().split())


def _exact_city(typed):
    """The slug of the one city named, or "" — never a guess.

    Upstream ranks by relevance, so its top hit for "Lyo" is a near miss dressed
    as an answer; and "Saint-Denis" is exactly right for both the 93 and the
    974. Hence exactly one exact match, or nothing: no city travels and les
    emplois shows its own search form.
    """
    wanted = _normalised(typed)
    # Labels read "Lyon (69)": the department disambiguates, it is not the name.
    slugs = {match["slug"] for match in city_matches(typed) if _normalised(match["label"].split("(")[0]) == wanted}
    return slugs.pop() if len(slugs) == 1 else ""


def search(request):
    """Dispatch the hero's single search form to the right external site.

    The target is never built from the request: "type" is only ever a key into
    `Hero.searches`. Building a URL from it would be an open redirect.
    """
    requested_type = Hero.resolve_search(request.GET.get("type", ""))
    target = Hero.searches[requested_type]

    # The slug comes from the autocomplete; with no JavaScript none can be
    # produced, so the typed name is resolved here instead. Les emplois only
    # ever receives the slug it already understands.
    city = request.GET.get("city", "").strip()
    if not city:
        city = _exact_city(request.GET.get("city_name", ""))

    params = {}
    if city:
        params["city"] = city
    # The thematic filter only means anything for "insertion": dropped for the
    # other two, whether stale or tampered with.
    if requested_type == "insertion":
        category = request.GET.get("category", "").strip()
        if category:
            params["category"] = category

    url = target.results_url
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    return redirect(url)
