"""The key-figures band, fed by the public open-data dashboard.

Which indicators are shown, in which order, and how they are labelled is
section content (see `accueil/sections/figures.py`). This module only turns a
list of indicator ids into current values, and never lets a slow or broken feed
take the page down: each indicator carries the last known value as a fallback.
"""

import json
import urllib.request

from django.core.cache import cache


FEED_URL = "https://statistiques.inclusion.gouv.fr/dashboards/chiffres-cles-plateforme/data.json"
CACHE_KEY = "key_figures"
CACHE_TTL = 3600  # seconds


def _format_french(number):
    # French thousands separator: a non-breaking space (e.g. 11 553).
    return f"{number:,}".replace(",", " ")


# A failed fetch is remembered only briefly: one blip should not pin the page
# to its fallbacks for a whole hour.
FAILURE_CACHE_TTL = 60  # seconds


def _feed():
    try:
        values = cache.get(CACHE_KEY)
    except Exception:
        return {}  # a cache outage must not take the page down
    if values is not None:
        return values

    values = {}
    fetched = False
    try:
        with urllib.request.urlopen(FEED_URL, timeout=5) as response:
            data = json.load(response)
        indicators = data.get("indicators", []) if isinstance(data, dict) else []
        values = {
            item["id"]: item["value"]
            for item in indicators
            # `isinstance(True, int)` is True, and a boolean would render as 1.
            if isinstance(item, dict) and "id" in item and type(item.get("value")) is int
        }
        fetched = True
    except Exception:
        pass  # any failure -> fall back to the values declared in the section

    try:
        cache.set(CACHE_KEY, values, CACHE_TTL if fetched else FAILURE_CACHE_TTL)
    except Exception:
        pass
    return values


def resolve(indicators):
    """Pair each declared indicator with its current value, formatted."""
    feed = _feed()
    resolved = []
    for indicator in indicators:
        value = feed.get(indicator.get("key"))
        if not isinstance(value, int):
            value = indicator.get("fallback") or 0
        resolved.append({**indicator, "value": _format_french(value)})
    return resolved
