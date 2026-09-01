from django.contrib.auth import get_user
from django.contrib.auth.models import User
from django.urls import reverse
from pytest_django.asserts import assertRedirects



def test_auto_login(db, client):
    response = client.get(reverse("edition:plan"))
    assertRedirects(
        response, reverse("admin:login") + "?next=%2Fedition%2F"
    )


def test_admin_auto_login(db, client):
    response = client.get(reverse("admin:index"))
    expected_url = reverse("admin:login") + "?next=%2Fadmin%2F"
    assertRedirects(response, expected_url)


def test_logout(db, client):
    user = User.objects.create(
        email="bob@example.test", first_name="bad", last_name="bad", is_staff=True, is_superuser=True
    )
    client.force_login(user)

    response = client.post(reverse("logout"))
    assertRedirects(response, reverse("index"))

    assert get_user(client).is_authenticated is False


def test_admin_logout(db, client):
    user = User.objects.create(
        email="bob@example.test", first_name="bad", last_name="bad", is_staff=True, is_superuser=True
    )
    client.force_login(user)

    response = client.post(reverse("admin:logout"))
    assertRedirects(response, reverse("index"))

    assert get_user(client).is_authenticated is False
