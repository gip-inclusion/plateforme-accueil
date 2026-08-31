import importlib

import pytest
from django.contrib.auth import get_user
from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import reverse
from pytest_django.asserts import assertRedirects


@pytest.fixture(name="oidc")
def setup_method():
    import config.urls

    # The backend refuses to instantiate without a full OIDC configuration; these
    # are the endpoints it checks for, pointing nowhere since nothing is fetched.
    with override_settings(
        OIDC_PROVIDER_URL="http://testserver",
        OIDC_RP_CLIENT_ID="test",
        OIDC_RP_CLIENT_SECRET="test",
        OIDC_RP_SIGN_ALGO="RS256",
        # These shiould be configured based on the previous
        OIDC_ENABLED=True,
        LOGIN_URL="oidc_authentication_init",
        OIDC_OP_TOKEN_ENDPOINT="https://testserver/application/o/token/",
        OIDC_OP_USER_ENDPOINT="https://testserver/application/o/userinfo/",
        OIDC_OP_JWKS_ENDPOINT="https://testserver/application/o/accueil-plateforme/jwks/",
    ):
        importlib.reload(config.urls)
        yield

    importlib.reload(config.urls)


def _backend():
    from accueil.auth import AuthentikBackend

    return AuthentikBackend()


def test_sso_user_creation(db, oidc):
    backend = _backend()
    user = backend.create_user({"email": "bob@example.test", "given_name": "Bob", "usual_name": "Beauregard"})
    assert not user.is_staff
    assert not user.is_superuser
    assert user.first_name == "Bob"
    assert user.last_name == "Beauregard"


def test_sso_user_update(db, oidc):
    User.objects.create(email="bob@example.test", first_name="bad", last_name="bad", is_staff=True, is_superuser=True)
    backend = _backend()
    user = backend.create_user({"email": "bob@example.test", "given_name": "Bob", "usual_name": "Beauregard"})
    # These are updated
    assert user.first_name == "Bob"
    assert user.last_name == "Beauregard"
    # There are not updated
    assert user.is_staff
    assert user.is_superuser


def test_auto_login(db, client, oidc):
    response = client.get(reverse("edition:plan"))
    assertRedirects(
        response, reverse("oidc_authentication_init") + "?next=%2Fedition%2F", fetch_redirect_response=False
    )


def test_admin_auto_login(db, client, oidc):
    response = client.get(reverse("admin:index"))
    expected_url = reverse("admin:login") + "?next=%2Fadmin%2F"
    assertRedirects(response, expected_url, fetch_redirect_response=False)

    response = client.get(expected_url)
    # We don't keep the next parameter as it's not used in the oidc callback
    assertRedirects(response, reverse("oidc_authentication_init"), fetch_redirect_response=False)


def test_logout(db, client, oidc):
    user = User.objects.create(
        email="bob@example.test", first_name="bad", last_name="bad", is_staff=True, is_superuser=True
    )
    client.force_login(user)

    response = client.post(reverse("logout"))
    assertRedirects(response, reverse("index"))

    assert get_user(client).is_authenticated is False


def test_admin_logout(db, client, oidc):
    user = User.objects.create(
        email="bob@example.test", first_name="bad", last_name="bad", is_staff=True, is_superuser=True
    )
    client.force_login(user)

    response = client.post(reverse("admin:logout"))
    assertRedirects(response, reverse("index"))

    assert get_user(client).is_authenticated is False
