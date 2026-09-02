"""City names resolved to the slugs "les emplois de l'inclusion" understands.

Their autocomplete is the single authority on what a name means, so both the
suggestions the page offers and the slug the search dispatch sends come from
here — the two can never disagree about the same term.

Proxied server-side because the endpoint sends no CORS headers, and the
embedded page lives in an opaque origin.
"""

import json
import unicodedata
import urllib.parse
import urllib.request

from django.core.cache import cache


CITIES_URL = "https://plateforme.inclusion.gouv.fr/autocomplete/cities"
CITIES_CACHE_TTL = 300  # seconds
CITIES_MAX = 8


def matches(term):
    """Cities matching a free-text term, each with the slug the result pages
    expect (e.g. "lyon-69")."""
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


def _normalised(name):
    """A city name reduced to what makes two spellings the same one."""
    folded = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return " ".join(folded.replace("-", " ").lower().split())


def exact_slug(typed):
    """The slug of the one city named, or "" — never a guess.

    Upstream ranks by relevance, so its top hit for "Lyo" is a near miss dressed
    as an answer; and "Saint-Denis" is exactly right for both the 93 and the
    974. Hence exactly one exact match, or nothing: no city travels and les
    emplois shows its own search form.
    """
    wanted = _normalised(typed)
    # Labels read "Lyon (69)": the department disambiguates, it is not the name.
    slugs = {match["slug"] for match in matches(typed) if _normalised(match["label"].split("(")[0]) == wanted}
    return slugs.pop() if len(slugs) == 1 else ""
