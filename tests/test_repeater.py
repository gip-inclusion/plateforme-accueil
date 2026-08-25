"""L'édition des listes répétables, élément par élément."""

import json

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.http import Http404
from django.shortcuts import resolve_url
from django.urls import reverse

from accueil import editing
from accueil.models import Section
from accueil.sections import registry


pytestmark = pytest.mark.django_db


@pytest.fixture
def page():
    call_command("sync_sections", verbosity=0)


@pytest.fixture
def editor(page):
    return User.objects.create_user("nadia", "nadia@example.test", "x", is_staff=True)


@pytest.fixture
def testimonials(page):
    return Section.objects.get(kind="testimonials")


@pytest.fixture
def figures(page):
    return Section.objects.get(kind="figures")


def declared(kind):
    return {section_type.key: section_type for section_type in registry.types()}[kind]


def test_an_untouched_list_reads_from_the_code(testimonials):
    values = editing.list_values(testimonials, declared("testimonials"), "quotes")
    assert values[0]["name"] == "Nadia B."


def test_saving_a_changed_list_records_an_override(testimonials):
    section_type = declared("testimonials")
    values = editing.list_values(testimonials, section_type, "quotes")
    values[0]["name"] = "Ana P."
    editing.save_list(testimonials, section_type, "quotes", values)

    testimonials.refresh_from_db()
    assert testimonials.content["quotes"][0]["name"] == "Ana P."


def test_saving_a_list_back_to_the_code_values_drops_the_override(figures):
    # `figures.indicators` — not `testimonials.quotes` — is the case that
    # actually exercises the cleaned-vs-cleaned comparison in `save_list`:
    # each `Indicator` carries an `image` (an `Illustration`), so cleaning
    # injects an `image_credit: ""` on every item. Comparing the cleaned list
    # against the *raw* `initial` (rather than the cleaned default) would
    # never match, and this override would never drop.
    section_type = declared("figures")
    values = editing.list_values(figures, section_type, "indicators")
    values[0]["label"] = "un libellé changé"
    editing.save_list(figures, section_type, "indicators", values)

    editing.save_list(figures, section_type, "indicators", section_type.defaults()["indicators"])

    figures.refresh_from_db()
    assert "indicators" not in figures.content


def test_a_list_that_breaks_its_own_rules_is_refused(testimonials):
    # `quotes` déclare min_num=1 : la liste ne peut pas devenir vide.
    with pytest.raises(ValidationError):
        editing.save_list(testimonials, declared("testimonials"), "quotes", [])
    testimonials.refresh_from_db()
    assert "quotes" not in testimonials.content


def test_an_unknown_list_name_is_a_404_not_a_500(testimonials):
    section_type = declared("testimonials")
    with pytest.raises(Http404):
        editing.list_values(testimonials, section_type, "does_not_exist")
    with pytest.raises(Http404):
        editing.save_list(testimonials, section_type, "does_not_exist", [])


def test_a_non_list_field_name_is_a_404_not_a_wrongly_saved_string(testimonials):
    # Without the guard, `Form.base_fields["title"].clean(["a", "b"])` returns
    # the *string* "['a', 'b']", which would then save straight into `content`
    # (`Section.clean`, the model-level guard, is never run by `save_list`).
    section_type = declared("testimonials")
    with pytest.raises(Http404):
        editing.save_list(testimonials, section_type, "title", ["a", "b"])
    with pytest.raises(Http404):
        editing.list_values(testimonials, section_type, "title")

    testimonials.refresh_from_db()
    assert "title" not in testimonials.content


def test_a_malformed_content_column_does_not_crash_the_helpers(testimonials):
    # `SectionType.__init__` already tolerates a non-dict `content`; these
    # helpers are meant to be a foundation as solid, not a step down from it.
    # A list, not `None`: the column is `NOT NULL`, so a JSON list is the
    # smallest malformed-but-storable value to exercise the guard against.
    testimonials.content = []
    testimonials.save(update_fields=["content"])

    section_type = declared("testimonials")
    values = editing.list_values(testimonials, section_type, "quotes")
    assert values[0]["name"] == "Nadia B."

    editing.save_list(testimonials, section_type, "quotes", values)
    testimonials.refresh_from_db()
    assert "quotes" not in (testimonials.content or {})


def post(client, name, row, field, index=None, data=None):
    args = [row.pk, field] if index is None else [row.pk, field, index]
    return client.post(reverse(f"edition:{name}", args=args), data or {})


def quotes(row):
    row.refresh_from_db()
    return editing.list_values(row, declared("testimonials"), "quotes")


def token(row):
    """The digest a legitimate POST must carry: over the list as it now reads."""
    return editing._digest(quotes(row))


def messages_of(response):
    # Not the private `_messages` on the request: iterating that consumes the
    # storage, so a second read on the same response would silently see
    # nothing. `get_messages` is the public, repeatable way to read it.
    return [str(message) for message in get_messages(response.wsgi_request)]


def test_duplicating_an_item_copies_it_right_after(client, editor, testimonials):
    client.force_login(editor)
    first = quotes(testimonials)[0]
    post(client, "item-duplicate", testimonials, "quotes", 0, {"token": token(testimonials)})
    after = quotes(testimonials)
    assert after[1]["quote"] == first["quote"]


def test_moving_an_item_swaps_it_with_its_neighbour(client, editor, testimonials):
    client.force_login(editor)
    names = [item["name"] for item in quotes(testimonials)]
    post(client, "item-move", testimonials, "quotes", 0, {"token": token(testimonials), "direction": "down"})
    assert [item["name"] for item in quotes(testimonials)] == [names[1], names[0]]


def test_deleting_an_item_removes_it(client, editor, testimonials):
    client.force_login(editor)
    names = [item["name"] for item in quotes(testimonials)]
    post(client, "item-delete", testimonials, "quotes", 0, {"token": token(testimonials)})
    assert [item["name"] for item in quotes(testimonials)] == names[1:]


def test_a_successful_operation_flashes_a_message(client, editor, testimonials):
    # Without JavaScript a successful move is otherwise a silent full page
    # reload — and, combined with the digest guard, an operation that hit the
    # wrong item would look exactly like one that hit the right one.
    client.force_login(editor)
    response = post(client, "item-delete", testimonials, "quotes", 0, {"token": token(testimonials)})
    assert any("mis à jour" in message for message in messages_of(response))


def test_deleting_the_last_item_is_refused_with_a_message(client, editor, testimonials):
    client.force_login(editor)
    for _ in range(len(quotes(testimonials)) - 1):
        post(client, "item-delete", testimonials, "quotes", 0, {"token": token(testimonials)})
    assert len(quotes(testimonials)) == 1

    response = post(client, "item-delete", testimonials, "quotes", 0, {"token": token(testimonials)})
    assert len(quotes(testimonials)) == 1
    assert any("au moins" in message for message in messages_of(response))


@pytest.mark.parametrize("name", ["item-duplicate", "item-delete", "item-move"])
def test_an_anonymous_post_is_redirected_and_still_denies_framing(client, testimonials, name):
    # `editor_view` carries more than a login check: it also applies
    # `xframe_options_deny` and the `frame-ancestors 'none'` override, so a
    # regression here would make a destructive endpoint public *and*
    # framable — assert both, on all three views, not just one.
    response = post(client, name, testimonials, "quotes", 0)
    assert response.status_code == 302
    assert response["Location"].startswith(resolve_url(settings.LOGIN_URL))
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert "quotes" not in Section.objects.get(pk=testimonials.pk).content


@pytest.mark.parametrize("name", ["item-duplicate", "item-delete", "item-move"])
def test_a_get_is_refused_and_still_denies_framing(client, editor, testimonials, name):
    client.force_login(editor)
    response = client.get(reverse(f"edition:{name}", args=[testimonials.pk, "quotes", 0]))
    assert response.status_code == 405
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_an_unknown_field_is_a_404(client, editor, testimonials):
    client.force_login(editor)
    assert post(client, "item-delete", testimonials, "inexistant", 0).status_code == 404


@pytest.mark.parametrize("name", ["item-duplicate", "item-delete", "item-move"])
def test_an_out_of_range_index_is_a_404(client, editor, testimonials, name):
    client.force_login(editor)
    out_of_range = len(quotes(testimonials))
    response = post(client, name, testimonials, "quotes", out_of_range, {"token": token(testimonials)})
    assert response.status_code == 404


def test_duplicating_past_max_num_is_refused_with_a_message(client, editor, testimonials):
    client.force_login(editor)
    while len(quotes(testimonials)) < 4:
        post(client, "item-duplicate", testimonials, "quotes", 0, {"token": token(testimonials)})
    assert len(quotes(testimonials)) == 4

    response = post(client, "item-duplicate", testimonials, "quotes", 0, {"token": token(testimonials)})
    assert len(quotes(testimonials)) == 4
    assert any("au plus" in message for message in messages_of(response))


def test_an_unreadable_override_is_left_untouched_by_a_list_operation(client, editor, testimonials):
    # An override that no longer validates (`min_num` tightened after the
    # fact, say) must not be silently replaced by the code's own content: the
    # first click on any operation would otherwise erase the editor's work
    # for good, with a success-shaped redirect and nothing recoverable.
    client.force_login(editor)
    testimonials.content = {"quotes": []}  # violates min_num=1: no longer validates
    testimonials.save(update_fields=["content"])
    stored_before = Section.objects.get(pk=testimonials.pk).content

    response = post(client, "item-delete", testimonials, "quotes", 0, {"token": "peu importe"})

    assert Section.objects.get(pk=testimonials.pk).content == stored_before
    assert any("n'est plus reconnue" in message for message in messages_of(response))


def test_a_missing_token_refuses_the_operation(client, editor, testimonials):
    client.force_login(editor)
    before = quotes(testimonials)

    response = post(client, "item-delete", testimonials, "quotes", 0)  # no token at all

    assert quotes(testimonials) == before
    assert any("a changé" in message for message in messages_of(response))


def test_a_stale_token_refuses_the_operation(client, editor, testimonials):
    # Reproduces the race: [A, B, C] is rendered and its digest captured: a
    # concurrent change lands first (someone else's delete), and the click on
    # the button for index 1 — meant for B — must not be let through against
    # a list that has since moved on, or it would silently hit C instead.
    client.force_login(editor)
    stale = token(testimonials)
    post(client, "item-delete", testimonials, "quotes", 0, {"token": stale})
    before = quotes(testimonials)

    response = post(client, "item-delete", testimonials, "quotes", 1, {"token": stale})

    assert quotes(testimonials) == before
    assert any("a changé" in message for message in messages_of(response))


def test_a_missing_direction_does_not_move_anything(client, editor, testimonials):
    client.force_login(editor)
    before = quotes(testimonials)

    post(client, "item-move", testimonials, "quotes", 0, {"token": token(testimonials)})

    assert quotes(testimonials) == before


def test_moving_the_first_item_up_is_a_no_op(client, editor, testimonials):
    # Correct only if the template withholds the "up" button on the first
    # item and the "down" button on the last — Task 10/11's contract to keep.
    client.force_login(editor)
    before = quotes(testimonials)

    post(client, "item-move", testimonials, "quotes", 0, {"token": token(testimonials), "direction": "up"})

    assert quotes(testimonials) == before


def test_an_item_is_edited_in_its_own_form(client, editor, testimonials):
    client.force_login(editor)
    url = reverse("edition:item", args=[testimonials.pk, "quotes", 0])
    body = client.get(url).content.decode()
    assert "Nadia B." in body

    response = client.post(
        url, {"token": token(testimonials), "quote": "Épatant.", "name": "Ana P.", "role": "Conseillère"}
    )
    assert response.status_code == 302
    assert quotes(testimonials)[0] == {"quote": "Épatant.", "name": "Ana P.", "role": "Conseillère"}


def test_an_invalid_item_is_shown_again_with_its_error(client, editor, testimonials):
    client.force_login(editor)
    url = reverse("edition:item", args=[testimonials.pk, "quotes", 0])
    response = client.post(url, {"token": token(testimonials), "quote": "", "name": "Ana P.", "role": ""})
    assert response.status_code == 200
    assert "quote" in response.context["form"].errors
    assert quotes(testimonials)[0]["name"] == "Nadia B."


def test_editing_an_item_without_a_token_is_refused(client, editor, testimonials):
    client.force_login(editor)
    url = reverse("edition:item", args=[testimonials.pk, "quotes", 0])

    response = client.post(url, {"quote": "Épatant.", "name": "Ana P.", "role": ""})  # no token at all

    assert quotes(testimonials)[0]["name"] == "Nadia B."
    assert any("a changé" in str(message) for message in get_messages(response.wsgi_request))


def test_editing_an_item_with_a_stale_token_is_refused(client, editor, testimonials):
    # Reproduces the same race `_apply`'s own stale-token test does: the
    # editor opens item 1 ("B"), someone else deletes item 0 in the
    # meantime, and B's form is submitted against a list that no longer has
    # B at index 1 — without the token, this would silently overwrite C.
    client.force_login(editor)
    stale = token(testimonials)
    post(client, "item-delete", testimonials, "quotes", 0, {"token": stale})
    before = quotes(testimonials)

    url = reverse("edition:item", args=[testimonials.pk, "quotes", 1])
    response = client.post(url, {"token": stale, "quote": "Usurpé.", "name": "Intrus", "role": ""})

    assert quotes(testimonials) == before
    assert any("a changé" in str(message) for message in get_messages(response.wsgi_request))


def test_an_item_form_accepts_a_file(client, editor, page):
    # Les indicateurs portent un pictogramme : le formulaire doit être
    # multipart, sinon le fichier n'arrive jamais.
    client.force_login(editor)
    figures = Section.objects.get(kind="figures")
    body = client.get(reverse("edition:item", args=[figures.pk, "indicators", 0])).content.decode()
    assert 'enctype="multipart/form-data"' in body


def test_an_out_of_range_item_is_a_404(client, editor, testimonials):
    client.force_login(editor)
    assert client.get(reverse("edition:item", args=[testimonials.pk, "quotes", 99])).status_code == 404


def test_adding_an_item_goes_through_a_form(client, editor, testimonials):
    # Insérer un élément vide échouerait sur une liste dont les champs sont
    # obligatoires : on passe par un formulaire, et la liste ne contient jamais
    # d'élément invalide.
    client.force_login(editor)
    url = reverse("edition:item-add", args=[testimonials.pk, "quotes"])
    assert client.get(url).status_code == 200

    before = len(quotes(testimonials))
    response = client.post(url, {"quote": "Rien à redire.", "name": "Ana P.", "role": ""})
    assert response.status_code == 302
    after = quotes(testimonials)
    assert len(after) == before + 1
    assert after[-1]["name"] == "Ana P."


def test_a_full_list_refuses_a_new_item(client, editor, testimonials):
    # `quotes` déclare max_num=4.
    client.force_login(editor)
    url = reverse("edition:item-add", args=[testimonials.pk, "quotes"])
    for rank in range(4):
        client.post(url, {"quote": f"Avis {rank}.", "name": f"Personne {rank}", "role": ""})
    assert len(quotes(testimonials)) == 4

    response = client.post(url, {"quote": "De trop.", "name": "Zoé", "role": ""})
    assert len(quotes(testimonials)) == 4
    assert any("au plus" in str(message) for message in get_messages(response.wsgi_request))


def test_a_profiles_item_is_created_and_edited_with_its_nested_list(client, editor, page):
    # `profiles.Profile.steps` is a *nested* `ListField`: `item_form_class`
    # maps it to the same raw-JSON `ListEditor` the section form already uses
    # for a top-level list — the floor that keeps `profiles` reachable at all
    # once Task 11 removes lists from the section form, not a proper
    # item-by-item editor for the nested repeater (out of scope here).
    client.force_login(editor)
    profiles = Section.objects.get(kind="profiles")
    section_type = declared("profiles")

    add_url = reverse("edition:item-add", args=[profiles.pk, "profiles"])
    steps = json.dumps([{"title": "Étape unique", "detail": ""}])
    response = client.post(
        add_url,
        {
            "slug": "nouveau",
            "tab_label": "Nouveau",
            "icon": "ri-star-line",
            "title": "Titre",
            "chapo": "",
            "cta_label": "Go",
            "cta_href": "https://example.test",
            "steps": steps,
        },
    )
    assert response.status_code == 302
    profiles.refresh_from_db()

    values = editing.list_values(profiles, section_type, "profiles")
    assert values[-1]["slug"] == "nouveau"
    assert values[-1]["steps"] == [{"title": "Étape unique", "detail": ""}]

    index = len(values) - 1
    edit_url = reverse("edition:item", args=[profiles.pk, "profiles", index])
    edit_token = editing._digest(values)
    body = client.get(edit_url).content.decode()
    assert "nouveau" in body

    new_steps = json.dumps([{"title": "Étape modifiée", "detail": "Un détail"}])
    response = client.post(
        edit_url,
        {
            "token": edit_token,
            "slug": "nouveau",
            "tab_label": "Nouveau",
            "icon": "ri-star-line",
            "title": "Titre modifié",
            "chapo": "",
            "cta_label": "Go",
            "cta_href": "https://example.test",
            "steps": new_steps,
        },
    )
    assert response.status_code == 302
    profiles.refresh_from_db()

    values = editing.list_values(profiles, section_type, "profiles")
    assert values[index]["title"] == "Titre modifié"
    assert values[index]["steps"] == [{"title": "Étape modifiée", "detail": "Un détail"}]
