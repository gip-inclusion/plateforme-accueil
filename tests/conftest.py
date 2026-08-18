import io
import json
from unittest import mock

import pytest
from django.core.cache import cache


# Canned key-figures feed served in place of the network by default.
KEY_FIGURES_FEED = {
    "indicators": [
        {"id": "offres_ouvertes", "value": 12345},
        {"id": "services_di", "value": 200000},
        {"id": "prescripteurs_actifs", "value": 6000},
    ]
}


@pytest.fixture(autouse=True)
def _isolated_cache():
    # Key-figures are cached per process; keep tests independent.
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def _mocked_feed():
    # Never reach the network in tests: serve the canned feed. A test that needs
    # the failure path re-patches urlopen to raise.
    def _response(*args, **kwargs):
        return io.BytesIO(json.dumps(KEY_FIGURES_FEED).encode())

    with mock.patch("accueil.views.urllib.request.urlopen", side_effect=_response):
        yield
