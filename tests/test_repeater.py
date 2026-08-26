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
from django.test import override_settings
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


@pytest.mark.parametrize(
    ("view", "expected"),
    [("item-delete", "supprimé"), ("item-duplicate", "dupliqué"), ("item-move", "déplacé")],
)
def test_a_successful_operation_says_which_one_it_was(client, editor, testimonials, view, expected):
    # Sans JavaScript, une opération réussie est sinon un rechargement muet —
    # et, avec la garde d'empreinte, une opération qui a frappé le mauvais
    # élément ressemblerait à une qui a frappé le bon. Surtout : dire « mis à
    # jour » après une suppression est le message qu'il ne faut pas se
    # permettre dans un chantier dont le sujet est de ne rien détruire.
    client.force_login(editor)
    data = {"token": token(testimonials)}
    if view == "item-move":
        data["direction"] = "down"
    response = post(client, view, testimonials, "quotes", 0, data)
    assert any(expected in message for message in messages_of(response))


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
    response = client.post(
        url, {"token": token(testimonials), "quote": "Rien à redire.", "name": "Ana P.", "role": ""}
    )
    assert response.status_code == 302
    after = quotes(testimonials)
    assert len(after) == before + 1
    assert after[-1]["name"] == "Ana P."


def test_a_full_list_refuses_a_new_item(client, editor, testimonials):
    # `quotes` déclare max_num=4.
    client.force_login(editor)
    url = reverse("edition:item-add", args=[testimonials.pk, "quotes"])
    for rank in range(4):
        client.post(
            url, {"token": token(testimonials), "quote": f"Avis {rank}.", "name": f"Personne {rank}", "role": ""}
        )
    assert len(quotes(testimonials)) == 4

    response = client.post(url, {"token": token(testimonials), "quote": "De trop.", "name": "Zoé", "role": ""})
    assert response.status_code == 200
    assert len(quotes(testimonials)) == 4
    assert any("au plus" in str(message) for message in get_messages(response.wsgi_request))
    # L'élément que l'éditeur venait de taper n'est pas perdu : la vue
    # réaffiche le formulaire lié plutôt que de rediriger vers la section.
    assert response.context["form"].data["name"] == "Zoé"


def test_adding_an_item_without_a_token_is_refused(client, editor, testimonials):
    client.force_login(editor)
    url = reverse("edition:item-add", args=[testimonials.pk, "quotes"])
    before = len(quotes(testimonials))

    response = client.post(url, {"quote": "Sans jeton.", "name": "Personne", "role": ""})

    assert len(quotes(testimonials)) == before
    assert any("a changé" in str(message) for message in get_messages(response.wsgi_request))


def test_adding_an_item_with_a_stale_token_is_refused(client, editor, testimonials):
    # Deux ajouts concurrents lisent la même liste : sans jeton, le second
    # écraserait le premier lors de l'écriture pleine-colonne de `save_list`,
    # et les deux éditeurs se verraient pourtant dire « Élément ajouté ».
    client.force_login(editor)
    url = reverse("edition:item-add", args=[testimonials.pk, "quotes"])
    stale = token(testimonials)
    client.post(url, {"token": stale, "quote": "Premier.", "name": "Un", "role": ""})
    before = quotes(testimonials)

    response = client.post(url, {"token": stale, "quote": "Second.", "name": "Deux", "role": ""})

    assert quotes(testimonials) == before
    assert any("a changé" in str(message) for message in get_messages(response.wsgi_request))


def test_adding_a_card_without_upload_support_is_refused_up_front(client, editor, page):
    # `search.Card.image` est obligatoire, sans `initial` : sans
    # téléversement configuré, l'écran d'ajout n'a aucun moyen de le
    # satisfaire — le refuser tout de suite évite un « Ce champ est
    # obligatoire. » pointant vers un contrôle absent de la page.
    client.force_login(editor)
    jobs = Section.objects.get(kind="jobs")
    url = reverse("edition:item-add", args=[jobs.pk, "cards"])

    with override_settings(UPLOADS_ENABLED=False):
        response = client.get(url)

    assert response.status_code == 302
    assert any("téléversement" in str(message) for message in get_messages(response.wsgi_request))


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
    add_token = editing._digest(editing.list_values(profiles, section_type, "profiles"))
    steps = json.dumps([{"title": "Étape unique", "detail": ""}])
    response = client.post(
        add_url,
        {
            "token": add_token,
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


def test_an_item_image_is_rendered_as_a_real_file_picker(client, editor, page):
    # Le ⚠ de la tâche 10 : un `Illustration` niché dans un item de liste doit
    # obtenir le même contrôle qu'un `Illustration` de section, pas rester un
    # simple champ texte affichant le chemin brut.
    client.force_login(editor)
    figures = Section.objects.get(kind="figures")
    body = client.get(reverse("edition:item", args=[figures.pk, "indicators", 0])).content.decode()
    assert 'class="champ-image"' in body
    assert 'name="image_current"' in body


def test_an_uploaded_file_travels_through_the_item_screen(client, editor, tmp_path, settings):
    # Sans multipart, ni lecture de `request.FILES`, le bouton s'affiche et
    # rien n'arrive : ce test pose un vrai fichier, pas seulement un attribut
    # d'accueil sur le formulaire.
    import io

    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image

    settings.MEDIA_ROOT = tmp_path
    settings.UPLOADS_ENABLED = True
    client.force_login(editor)
    figures = Section.objects.get(kind="figures")
    section_type = declared("figures")
    url = reverse("edition:item", args=[figures.pk, "indicators", 0])

    form = client.get(url).context["form"]
    data = {bound.name: bound.value() if bound.value() is not None else "" for bound in form}
    values = editing.list_values(figures, section_type, "indicators")
    data["token"] = editing._digest(values)
    data["image_current"] = values[0]["image"]

    buffer = io.BytesIO()
    Image.new("RGB", (400, 300), (10, 20, 30)).save(buffer, format="PNG")
    data["image"] = SimpleUploadedFile("neuf.png", buffer.getvalue(), content_type="image/png")

    response = client.post(url, data)
    assert response.status_code == 302
    figures.refresh_from_db()
    after = editing.list_values(figures, section_type, "indicators")
    assert after[0]["image"].startswith("uploads/")


def test_an_unreadable_override_refuses_to_open_an_item(client, editor, testimonials):
    client.force_login(editor)
    testimonials.content = {"quotes": []}  # violates min_num=1: no longer validates
    testimonials.save(update_fields=["content"])

    response = client.get(reverse("edition:item", args=[testimonials.pk, "quotes", 0]))

    assert response.status_code == 302
    assert any("n'est plus reconnue" in str(message) for message in get_messages(response.wsgi_request))


def test_an_unreadable_override_refuses_to_open_the_add_screen(client, editor, testimonials):
    client.force_login(editor)
    testimonials.content = {"quotes": []}  # violates min_num=1: no longer validates
    testimonials.save(update_fields=["content"])

    response = client.get(reverse("edition:item-add", args=[testimonials.pk, "quotes"]))

    assert response.status_code == 302
    assert any("n'est plus reconnue" in str(message) for message in get_messages(response.wsgi_request))


def test_editing_an_out_of_range_item_with_a_current_token_is_a_404(client, editor, testimonials):
    # Un jeton à jour ne rend pas un index hors bornes valide : sans le
    # contrôle, `values[index] = …` lèverait `IndexError` (une 500), plutôt
    # que le 404 qu'un index qui n'existe pas doit produire.
    client.force_login(editor)
    out_of_range = len(quotes(testimonials))
    url = reverse("edition:item", args=[testimonials.pk, "quotes", out_of_range])

    response = client.post(url, {"token": token(testimonials), "quote": "X", "name": "Y", "role": ""})

    assert response.status_code == 404


def test_a_colliding_slug_re_renders_the_form_instead_of_losing_it(client, editor, page):
    # `profiles` déclare `unique="slug"` : faire entrer en collision deux
    # profils est refusé par `save_list`, whole-list. La règle de la tâche :
    # ce refus réaffiche le formulaire lié, il ne redirige pas et n'efface
    # rien de ce que l'éditeur vient de saisir.
    client.force_login(editor)
    profiles_row = Section.objects.get(kind="profiles")
    section_type = declared("profiles")
    values = editing.list_values(profiles_row, section_type, "profiles")
    other_slug = values[1]["slug"]

    edit_url = reverse("edition:item", args=[profiles_row.pk, "profiles", 0])
    steps = json.dumps(values[0]["steps"])
    response = client.post(
        edit_url,
        {
            "token": editing._digest(values),
            "slug": other_slug,  # collides with values[1]
            "tab_label": values[0]["tab_label"],
            "icon": values[0]["icon"],
            "title": "Titre saisi à l'instant",
            "chapo": "",
            "cta_label": values[0]["cta_label"],
            "cta_href": values[0]["cta_href"],
            "steps": steps,
        },
    )

    assert response.status_code == 200
    assert response.context["form"].data["title"] == "Titre saisi à l'instant"
    unchanged = editing.list_values(profiles_row, section_type, "profiles")
    assert unchanged[0]["slug"] != other_slug


def test_a_preview_splits_an_item_by_what_it_declares(figures):
    # `figures.indicators` (`Indicator`, in accueil/sections/figures.py):
    # `key` is a `Reference`, `label` a short text field, `image` an
    # `Illustration`, `fallback` an `IntegerField`. `image_credit` is
    # injected as a `Credit` by `add_credit_fields`.
    from accueil.previews import item_parts

    section_type = declared("figures")
    field = section_type.Form.base_fields["indicators"]
    values = editing.list_values(figures, section_type, "indicators")

    parts = item_parts(field, values[0])

    assert parts["image"] == values[0]["image"]
    assert parts["title"] == values[0]["label"]
    assert parts["paragraphs"] == []
    assert ("Identifiant dans le flux", values[0]["key"]) in parts["settings"]
    assert ("Valeur de repli", values[0]["fallback"]) in parts["settings"]


def test_a_long_text_field_is_kept_whole_in_a_preview(testimonials):
    # `testimonials.quotes` (`Quote`): `quote` is a `Textarea`, kept in full —
    # never truncated, never summarised to a single line.
    from accueil.previews import item_parts

    section_type = declared("testimonials")
    field = section_type.Form.base_fields["quotes"]
    values = editing.list_values(testimonials, section_type, "quotes")

    parts = item_parts(field, values[0])

    assert parts["paragraphs"] == [values[0]["quote"]]


def test_a_credit_never_appears_in_a_preview(testimonials):
    # `illustration_credit` on `testimonials`' own fields is out of scope
    # here (it is not a list item); `figures.indicators`' `image_credit` is
    # the one injected onto every item by `add_credit_fields`, and it must
    # never surface as a title, a paragraph, a detail or a setting.
    from accueil.previews import item_parts

    figures_row = Section.objects.get(kind="figures")
    section_type = declared("figures")
    field = section_type.Form.base_fields["indicators"]
    values = editing.list_values(figures_row, section_type, "indicators")
    values[0]["image_credit"] = "Une mention de provenance"

    parts = item_parts(field, values[0])

    rendered = repr(parts)
    assert "image_credit" not in rendered
    assert "Une mention de provenance" not in rendered


def test_section_lists_reports_add_and_delete_eligibility(figures):
    # `figures.indicators` déclare min_num=1, max_num=4 ; le fixture en pose
    # trois : ajouter doit rester permis, supprimer aussi.
    from accueil.previews import section_lists

    section_type = declared("figures")
    content = section_type(figures.content).content

    boards = section_lists(section_type, content)
    board = next(board for board in boards if board["name"] == "indicators")

    assert board["can_add"] is True
    assert board["can_delete"] is True
    assert len(board["items"]) == 3
    assert board["items"][0]["index"] == 0
    assert board["items"][-1]["last"] is True


def test_the_section_screen_shows_every_item_in_full(client, editor, testimonials):
    # No summary, no truncation, no carousel: every declared bit of an item
    # must be readable directly on the section screen.
    from django.utils.html import escape

    client.force_login(editor)
    values = editing.list_values(testimonials, declared("testimonials"), "quotes")

    body = client.get(reverse("edition:section", args=[testimonials.pk])).content.decode()

    for item in values:
        assert escape(item["quote"]) in body
        assert escape(item["name"]) in body


def test_the_section_form_no_longer_carries_the_lists(client, editor, testimonials):
    # Task 11: the lists move to their own board; the section form keeps the
    # section's other, simple fields.
    client.force_login(editor)
    response = client.get(reverse("edition:section", args=[testimonials.pk]))

    assert "quotes" not in response.context["form"].fields
    assert "kicker" in response.context["form"].fields
    assert "title" in response.context["form"].fields


def test_an_unreadable_list_is_not_shown_as_though_it_were_the_editors(client, editor, testimonials):
    # `list_values` (and so `section_lists`, built from the same merged
    # content) would silently fall back to the code's own items once an
    # override no longer validates. The section screen must not display
    # those as though they belonged to the editor: it shows a warning
    # instead of the board, with a way back to the code.
    client.force_login(editor)
    testimonials.content = {"quotes": []}  # violates min_num=1: no longer validates
    testimonials.save(update_fields=["content"])

    response = client.get(reverse("edition:section", args=[testimonials.pk]))
    body = response.content.decode()

    assert "n'est plus reconnue" in body
    assert "Nadia B." not in body  # the code's own content is not shown as a stand-in
    assert not any(board["name"] == "quotes" for board in response.context["boards"])


def test_saving_a_section_with_an_unreadable_list_override_does_not_crash(client, editor, testimonials):
    # Regression: `SectionForm.clean` preserves an unreadable override
    # untouched into `self.instance.content`; `_post_clean` then runs
    # `Section.clean` (the model) against it, which rejects it keyed on
    # "content" — a field this form does not carry. Django's own
    # `_update_errors` cannot attach that and used to raise `ValueError`
    # instead of a `ValidationError`: a 500 on every save of a section
    # carrying this, not just on an operation touching the broken list.
    testimonials.content = {"quotes": []}  # violates min_num=1: no longer validates
    testimonials.save(update_fields=["content"])
    stored_before = Section.objects.get(pk=testimonials.pk).content

    client.force_login(editor)
    defaults = declared("testimonials").defaults()
    data = {
        "position": testimonials.position,
        "active": "on",
        "kicker": defaults["kicker"],
        "title": "Un titre neuf",
        "illustration_current": defaults["illustration"],
        "illustration_credit": "",
    }
    response = client.post(reverse("edition:section", args=[testimonials.pk]), data)

    assert response.status_code == 200  # redisplayed with the error, not a 500
    errors = [str(error) for error in response.context["form"].non_field_errors()]
    # The list's declared *label* ("Témoignages"), never its English field
    # identifier ("quotes") — identifiers are English precisely because
    # they are never shown to an editor (CLAUDE.md).
    assert any("Témoignages" in error for error in errors)
    assert not any("quotes" in error for error in errors)
    assert Section.objects.get(pk=testimonials.pk).content == stored_before
    # The warning box, with its own path back to the code, is right there too.
    assert "n'est plus reconnue" in response.content.decode()


def test_the_title_heuristic_never_promotes_an_icon():
    # Run over every declared list in the registry, not just the two cases
    # the icon-first bug was found on: a heuristic this generic must hold
    # everywhere, not just where someone happened to look.
    from accueil.previews import item_parts
    from accueil.sections.base import ListField

    checked = 0
    for section_type in registry.types():
        for field in section_type.Form.base_fields.values():
            if not isinstance(field, ListField) or not field.initial:
                continue
            for item in field.initial:
                if "icon" not in item:
                    continue
                parts = item_parts(field, item)
                checked += 1
                assert parts["title"] != item["icon"]
    assert checked > 0


def test_advisors_tags_title_is_the_label_not_the_icon():
    from accueil.previews import item_parts
    from accueil.sections.advisors import Advisors

    field = Advisors.Form.base_fields["tags"]
    first = field.initial[0]

    parts = item_parts(field, first)

    assert parts["title"] == first["label"]


def test_features_steps_title_is_the_title_field_not_the_icon():
    from accueil.previews import item_parts
    from accueil.sections.features import Features

    field = Features.Form.base_fields["steps"]
    first = field.initial[0]

    parts = item_parts(field, first)

    assert parts["title"] == first["title"]


def test_a_nested_list_field_renders_as_a_count_not_a_repr():
    # `profiles.Profile.steps` is a `ListField` nested inside another list's
    # item form. Its default widget is a plain `TextInput`, so without
    # special handling it falls through to `details` as a raw Python repr
    # of a list of dicts — exactly the kind of thing this board exists to
    # stop showing.
    from accueil.previews import item_parts
    from accueil.sections.profiles import Profiles

    field = Profiles.Form.base_fields["profiles"]
    first = field.initial[0]

    parts = item_parts(field, first)

    rendered = repr(parts)
    assert "'detail':" not in rendered  # no raw dump of the nested steps' own fields
    assert any(str(len(first["steps"])) in str(value) for _, value in parts["details"])


def test_an_empty_optional_field_is_left_out_of_the_details():
    from accueil.previews import item_parts

    field = declared("testimonials").Form.base_fields["quotes"]
    item = {"quote": "Un avis.", "name": "Ana", "role": ""}

    parts = item_parts(field, item)

    assert not any(label == "Fonction" for label, _ in parts["details"])


def test_can_add_accounts_for_uploads_being_disabled(client, editor, figures, settings):
    # `figures.Indicator.image` is a required `Illustration` with no
    # `initial`: adding a new indicator is structurally impossible without
    # uploads configured (`_blocks_creation_without_uploads`), which the
    # board's own `can_add` (from `min_num`/`max_num` alone) cannot know.
    settings.UPLOADS_ENABLED = False
    client.force_login(editor)

    response = client.get(reverse("edition:section", args=[figures.pk]))
    board = next(board for board in response.context["boards"] if board["name"] == "indicators")

    assert board["can_add"] is False


def test_the_unreadable_warning_shows_the_raw_stored_content(client, editor, testimonials):
    # The board's only way out (below) drops the override for good, and the
    # admin's own textarea shows the same already-fallen-back content this
    # screen would — so the raw JSON must be readable here, to copy out
    # before either happens.
    client.force_login(editor)
    testimonials.content = {"quotes": []}
    testimonials.save(update_fields=["content"])

    body = client.get(reverse("edition:section", args=[testimonials.pk])).content.decode()

    assert '<pre class="liste-illisible__brut">[]</pre>' in body


def test_an_overridden_list_gets_its_own_labelled_control(client, editor, testimonials):
    # A list's own reset is destructive in a different way than a one-line
    # `kicker`'s: it must not sit, indistinguishable, in the generic
    # "revenir au texte du code" list at the bottom.
    client.force_login(editor)
    testimonials.content = {"quotes": [{"quote": "Un avis modifié.", "name": "Ana", "role": ""}]}
    testimonials.save(update_fields=["content"])

    response = client.get(reverse("edition:section", args=[testimonials.pk]))
    body = response.content.decode()

    assert "quotes" not in response.context["overridden"]
    assert "Supprimer ces modifications et revenir aux éléments du code" in body
    assert "<code>quotes</code>" not in body


def test_every_item_control_carries_the_concurrency_token(client, editor, testimonials):
    # Mutation-proof: a template that dropped the hidden token from a
    # control would still pass every functional test (every button would
    # just always refuse), and the suite would stay green.
    client.force_login(editor)
    values = editing.list_values(testimonials, declared("testimonials"), "quotes")

    body = client.get(reverse("edition:section", args=[testimonials.pk])).content.decode()

    # move + duplicate + delete: three controls per item, each carrying it.
    assert body.count('name="token"') == 3 * len(values)


def test_move_buttons_are_disabled_at_the_ends_only(client, editor, testimonials):
    # Mutation-proof: removing every `disabled` (or adding it everywhere)
    # must be caught, not just the functional no-op it produces.
    client.force_login(editor)

    body = client.get(reverse("edition:section", args=[testimonials.pk])).content.decode()

    assert body.count('aria-label="Monter cet élément" disabled') == 1
    assert body.count('aria-label="Descendre cet élément" disabled') == 1


def test_a_successful_save_never_builds_the_boards(client, editor, testimonials, monkeypatch):
    # The boards (and the unreadable-override check behind them) are wasted
    # work on a POST that is about to redirect away: `_boards` must only run
    # when the screen is actually about to render.
    import accueil.editing as editing_module

    original = editing_module._boards
    calls = []

    def spy(row, section_type):
        calls.append((row, section_type))
        return original(row, section_type)

    monkeypatch.setattr(editing_module, "_boards", spy)

    client.force_login(editor)
    defaults = declared("testimonials").defaults()
    data = {
        "position": testimonials.position,
        "active": "on",
        "kicker": defaults["kicker"],
        "title": "Encore un autre titre.",
        "illustration_current": defaults["illustration"],
        "illustration_credit": "",
    }
    response = client.post(reverse("edition:section", args=[testimonials.pk]), data)

    assert response.status_code == 302
    assert calls == []


@pytest.mark.parametrize(
    "kind, name, label",
    [
        ("testimonials", "quotes", "Témoignages"),
        ("figures", "indicators", "Indicateurs"),
        ("jobs", "cards", "Cartes en avant"),
        ("features", "steps", "Étapes"),
        ("advisors", "tags", "Exemples de structures"),
    ],
)
def test_the_model_error_names_the_list_by_its_label_not_its_identifier(page, kind, name, label):
    # `Section.clean` (the model) is where this message is built, and it
    # reaches an editor as a form-wide error (`SectionForm._update_errors`).
    # `name` is the field's English identifier — never meant to be shown,
    # per CLAUDE.md — while `label` is what the section itself declares as
    # the list's French name.
    row = Section.objects.get(kind=kind)
    row.content = {name: []}  # violates min_num=1 on every one of these lists

    with pytest.raises(ValidationError) as excinfo:
        row.full_clean()

    message = str(excinfo.value)
    assert label in message
    assert name not in message


# Closure of every new screen this branch added: `item`, `item-add`,
# `item-duplicate`, `item-move`, `item-delete`. The three destructive ones
# already have their own anonymous-POST and GET-refuses-405 coverage above;
# what is missing is systematic across *all five* — an anonymous GET, and a
# signed-in but non-staff visitor — parametrised rather than five near-copies.

ALL_ITEM_VIEWS = ["item", "item-add", "item-duplicate", "item-move", "item-delete"]


def _item_view_url(name, row, field="quotes", index=0):
    args = [row.pk, field] if name == "item-add" else [row.pk, field, index]
    return reverse(f"edition:{name}", args=args)


@pytest.fixture
def visitor(page):
    return User.objects.create_user("bob", "bob@example.test", "x")


@pytest.mark.parametrize("name", ALL_ITEM_VIEWS)
def test_an_anonymous_get_is_refused_and_still_denies_framing(client, testimonials, name):
    # `editor_required` runs before `require_POST`, so an anonymous GET is
    # refused the same way on all five screens, not just the three that are
    # POST-only.
    response = client.get(_item_view_url(name, testimonials))
    assert response.status_code == 302
    assert response["Location"].startswith(resolve_url(settings.LOGIN_URL))
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


@pytest.mark.parametrize("name", ["item", "item-add"])
def test_an_anonymous_post_is_also_refused_on_the_get_capable_screens(client, testimonials, name):
    # The three destructive views already have this above; `item` and
    # `item-add` accept a POST too and are not covered by that parametrize.
    response = client.post(_item_view_url(name, testimonials), {"token": "peu importe"})
    assert response.status_code == 302
    assert response["Location"].startswith(resolve_url(settings.LOGIN_URL))
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


@pytest.mark.parametrize("name", ALL_ITEM_VIEWS)
def test_a_non_staff_visitor_is_refused_every_list_item_screen(client, visitor, testimonials, name):
    # Not previously exercised at all for any of these five: only the plan
    # view (`test_a_visitor_without_staff_is_refused`, in test_editing.py) was
    # checked against a signed-in, non-staff account.
    client.login(username="bob", password="x")
    response = client.get(_item_view_url(name, testimonials))
    assert response.status_code == 302
    assert "/edition/" not in response["Location"].split("?")[0]
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
