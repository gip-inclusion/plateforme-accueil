"""The icon field: what it offers, and how the picker renders."""

import re

import pytest
from django.core.management import call_command
from django.urls import reverse

from accueil.sections import advisors, features, profiles, search
from accueil.sections.base import Icon, IconWidget, sprite_icon_names


@pytest.fixture
def page():
    call_command("sync_sections", verbosity=0)


@pytest.fixture
def editor(page):
    from django.contrib.auth.models import User

    return User.objects.create_user("nadia", "nadia@example.test", "x", is_staff=True)


def test_an_icon_field_offers_exactly_the_sprite_symbols():
    # Choices come from the sprite itself, so there is no second list that
    # could drift from it.
    field = Icon(label="Icône")
    offered = {value for value, label in field.choices}
    assert offered == set(sprite_icon_names())


def test_an_icon_field_carries_its_own_widget_with_no_extra_mapping():
    # An icon id needs no transformation between the declared field and the
    # one an editor sees, so `Icon` carries its widget directly.
    field = Icon(label="Icône")
    assert isinstance(field.widget, IconWidget)


def test_a_sprite_icon_is_accepted():
    field = Icon(label="Icône")
    assert field.clean("ri-briefcase-line") == "ri-briefcase-line"


def test_an_icon_outside_the_sprite_is_a_form_error():
    field = Icon(label="Icône")
    with pytest.raises(Exception) as excinfo:
        field.clean("ri-alien-line")
    assert "valide" in str(excinfo.value) or "choice" in str(excinfo.value).lower()


@pytest.mark.parametrize(
    "form_class",
    [search.Card, search.Shortcut, features.Step, advisors.Tag, profiles.Profile],
)
def test_the_item_forms_declare_an_icon_field(form_class):
    assert isinstance(form_class.base_fields["icon"], Icon)


@pytest.mark.django_db
def test_the_rendered_widget_offers_a_radio_per_sprite_icon(client, editor):
    client.force_login(editor)
    from accueil.models import Section

    row = Section.objects.get(kind="features")
    url = reverse("edition:item", args=[row.pk, "steps", 0])
    body = client.get(url).content.decode()

    # One radio per sprite icon, each showing the glyph the page draws.
    assert body.count('type="radio"') >= len(sprite_icon_names())
    assert '<use href="#ri-briefcase-line"/>' in body
    briefcase_input = re.search(r'<input type="radio"[^>]*value="ri-briefcase-line"[^>]*>', body)
    assert briefcase_input and "checked" in briefcase_input.group()


@pytest.mark.django_db
def test_an_icon_choice_saves_with_no_javascript(client, editor):
    # Ordinary radios: picking an icon needs no script.
    client.force_login(editor)
    from accueil.models import Section

    row = Section.objects.get(kind="features")
    url = reverse("edition:item", args=[row.pk, "steps", 0])

    context = client.get(url).context
    form = context["form"]
    data = {bound.name: bound.value() if bound.value() is not None else "" for bound in form}
    data["icon"] = "ri-plant-line"
    data["token"] = context["token"]

    response = client.post(url, data)
    assert response.status_code == 302
    row.refresh_from_db()
    assert row.content["steps"][0]["icon"] == "ri-plant-line"


@pytest.mark.django_db
def test_an_icon_outside_the_sprite_is_rejected_by_the_item_form(client, editor):
    client.force_login(editor)
    from accueil.models import Section

    row = Section.objects.get(kind="features")
    url = reverse("edition:item", args=[row.pk, "steps", 0])

    context = client.get(url).context
    form = context["form"]
    data = {bound.name: bound.value() if bound.value() is not None else "" for bound in form}
    data["icon"] = "ri-alien-line"
    data["token"] = context["token"]

    response = client.post(url, data)
    assert response.status_code == 200
    assert response.context["form"].errors["icon"]


def test_the_public_page_is_unchanged(client):
    # The public page still sees plain text: the picker is an editing screen
    # only.
    response = client.get("/")
    body = response.content.decode()
    assert "champ-icone" not in body
    assert '<use href="#ri-briefcase-line"/>' in body
