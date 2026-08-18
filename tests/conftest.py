import io
import json
from unittest import mock

import pytest
from django.conf import settings
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
    # Never reach the network in tests: serve the canned feed to both callers
    # (the key figures and the city proxy). A test that needs the failure path
    # re-patches urlopen to raise.
    def _response(*args, **kwargs):
        return io.BytesIO(json.dumps(KEY_FIGURES_FEED).encode())

    with mock.patch("urllib.request.urlopen", side_effect=_response):
        yield


def pytest_collection_modifyitems(config, items):
    # The database is optional for this project; without DATABASE_URL the CMS
    # tests have nothing to talk to, and the rest of the suite still runs.
    if settings.DATABASE_CONFIGURED:
        return
    skip = pytest.mark.skip(reason="pas de DATABASE_URL")
    for item in items:
        if "django_db" in item.keywords:
            item.add_marker(skip)
