"""Le champ image : déclaration, provenance, résolution en URL."""

import copy
import re
from collections import Counter

import pytest
from django import forms
from django.conf import settings
from django.template import Context, Template
from django.template.loader import get_template
from django.test import Client, override_settings

from accueil.sections import registry
from accueil.sections.base import Credit, Illustration, ListField, Registry, SectionType, add_credit_fields
from accueil.templatetags.illustrations import illustration


def test_an_illustration_is_text_shaped():
    # La valeur reste une chaîne : c'est ce qui préserve `check_shape`,
    # la comparaison au défaut et le stockage-des-écarts.
    field = Illustration(max_width=800, ratio=(16, 10), initial="accueil/img/x.webp")
    assert field.clean("accueil/img/x.webp") == "accueil/img/x.webp"
    assert field.max_width == 800
    assert field.ratio == (16, 10)


def test_a_section_gets_a_credit_field_for_each_illustration():
    registry = Registry()

    @registry.register
    class Banner(SectionType):
        key = "banner"
        label = "Bandeau"
        template = "x.html"

        class Form(forms.Form):
            visual = Illustration(max_width=800, initial="accueil/img/x.webp")

    credit = Banner.Form.base_fields["visual_credit"]
    assert isinstance(credit, Credit)
    assert credit.required is False
    # Un défaut vide, pour que `defaults()` reste une chaîne.
    assert Banner.defaults()["visual_credit"] == ""


def test_items_of_a_list_get_their_credit_field_too():
    class Item(forms.Form):
        image = Illustration(max_width=400, initial="accueil/img/x.webp")

    ListField(Item)
    assert isinstance(Item.base_fields["image_credit"], Credit)


def test_ratio_defaults_to_none():
    field = Illustration(max_width=800, initial="accueil/img/x.webp")
    assert field.ratio is None


def test_max_width_and_ratio_survive_deepcopy():
    # `section_form_class` et `SectionType.defaults()` déclenchent tous deux
    # une copie profonde des champs déclarés : cet invariant leur est acquis.
    field = Illustration(max_width=800, ratio=(16, 10), initial="accueil/img/x.webp")
    clone = copy.deepcopy(field)
    assert clone.max_width == 800
    assert clone.ratio == (16, 10)


def test_credit_label_falls_back_when_the_illustration_has_none():
    class Form(forms.Form):
        visual = Illustration(max_width=800, initial="accueil/img/x.webp")

    add_credit_fields(Form)
    assert Form.base_fields["visual_credit"].label == "Provenance de l'image"


def test_credit_fields_are_ordered_right_after_their_illustration():
    class Form(forms.Form):
        visual = Illustration(max_width=800, initial="accueil/img/a.webp")
        title = forms.CharField(initial="Titre")
        banner = Illustration(max_width=400, initial="accueil/img/b.webp")

    add_credit_fields(Form)
    assert list(Form.base_fields.keys()) == [
        "visual",
        "visual_credit",
        "title",
        "banner",
        "banner_credit",
    ]
    # Le champ de provenance se repère par son illustration, sans parser son nom.
    assert Form.base_fields["visual_credit"].illustration_name == "visual"
    assert Form.base_fields["banner_credit"].illustration_name == "banner"


def test_add_credit_fields_is_idempotent():
    class Form(forms.Form):
        visual = Illustration(max_width=800, initial="accueil/img/x.webp")

    add_credit_fields(Form)
    first_credit = Form.base_fields["visual_credit"]
    add_credit_fields(Form)
    assert Form.base_fields["visual_credit"] is first_credit
    assert list(Form.base_fields.keys()) == ["visual", "visual_credit"]


def test_add_credit_fields_respects_a_hand_declared_credit():
    class CustomCredit(forms.CharField):
        pass

    class Form(forms.Form):
        visual = Illustration(max_width=800, initial="accueil/img/x.webp")
        visual_credit = CustomCredit(required=True)

    add_credit_fields(Form)
    assert isinstance(Form.base_fields["visual_credit"], CustomCredit)
    assert Form.base_fields["visual_credit"].required is True


def test_a_subclass_of_a_processed_form_keeps_the_credit_field():
    class Form(forms.Form):
        visual = Illustration(max_width=800, initial="accueil/img/x.webp")

    add_credit_fields(Form)

    class Subform(Form):
        pass

    assert isinstance(Subform.base_fields["visual_credit"], Credit)


def test_illustration_name_survives_deepcopy_and_a_form_instance():
    class Form(forms.Form):
        visual = Illustration(max_width=800, initial="accueil/img/x.webp")

    add_credit_fields(Form)
    credit_field = Form.base_fields["visual_credit"]

    clone = copy.deepcopy(credit_field)
    assert clone.illustration_name == "visual"

    bound_form = Form()
    assert bound_form.fields["visual_credit"].illustration_name == "visual"


def test_a_code_path_resolves_through_staticfiles():
    assert illustration("accueil/img/hero.webp").endswith("accueil/img/hero.webp")
    assert illustration("accueil/img/hero.webp").startswith(settings.STATIC_URL)


class StubStorage:
    """Un backend factice : renvoie une sentinelle, pour vérifier que le
    filtre délègue bien à la storage plutôt que de concaténer `MEDIA_URL`."""

    def url(self, name):
        return f"https://cdn.example.test/{name}"


class RaisingStorage:
    """Simule une storage qui construit sans erreur mais échoue à l'usage :
    `url()` explose, par exemple un bucket S3 injoignable au moment de l'appel."""

    def url(self, name):
        raise Exception("boom")


class BrokenAtConstructionStorage:
    """Simule un réglage `STORAGES` invalide dès l'instanciation — le cas qui
    ne serait PAS couvert si le garde-fou se contentait de protéger `url()` :
    `storages["default"]` construit paresseusement le backend au premier accès,
    en plein rendu du template."""

    def __init__(self, *args, **kwargs):
        raise Exception("boom at construction")


@override_settings(STORAGES={"default": {"BACKEND": f"{__name__}.StubStorage"}})
def test_an_upload_key_resolves_through_the_media_store():
    # Une simple concaténation de MEDIA_URL donnerait aussi ce résultat sur un
    # backend fichier ; ce stub prouve que c'est bien la storage qui décide.
    assert illustration("uploads/abc123.webp") == "https://cdn.example.test/uploads/abc123.webp"


def test_an_empty_value_gives_an_empty_string():
    # Un champ vide ne doit pas produire `/static/` tout court, qui ferait une
    # requête inutile et une image cassée.
    assert illustration("") == ""
    assert illustration(None) == ""


def test_a_non_string_value_gives_an_empty_string():
    # Le filtre est appelé depuis un template : il ne doit jamais lever.
    assert illustration(42) == ""


def test_a_path_escaping_the_static_prefix_gives_an_empty_string():
    # `urljoin` gomme les `..` et peut sortir de STATIC_URL : une valeur du
    # code n'a rien à faire hors du préfixe statique.
    assert illustration("../../etc/passwd") == ""
    assert illustration("accueil/img/../../../etc/passwd") == ""


@override_settings(STORAGES={"default": {"BACKEND": f"{__name__}.RaisingStorage"}})
def test_a_broken_storage_gives_an_empty_string_instead_of_a_500():
    # La page publique importe plus que l'image : une storage mal configurée
    # (bucket S3 absent, credentials invalides) ne doit jamais faire tomber le
    # rendu du template.
    assert illustration("uploads/abc123.webp") == ""


@override_settings(STORAGES={"default": {"BACKEND": f"{__name__}.BrokenAtConstructionStorage"}})
def test_a_storage_failing_at_construction_gives_an_empty_string_instead_of_a_500():
    # C'est le cas qui compte vraiment : `storages["default"]` instancie le
    # backend paresseusement, ici, en plein rendu. Un simple `try` autour de
    # `url()` ne le couvrirait pas si quelqu'un remontait la storage en dehors
    # du bloc protégé.
    assert illustration("uploads/abc123.webp") == ""


def test_the_filter_is_usable_from_a_template():
    rendered = Template("{% load illustrations %}{{ path|illustration }}").render(
        Context({"path": "accueil/img/hero.webp"})
    )
    assert rendered.startswith(settings.STATIC_URL)


@pytest.mark.parametrize(("key", "name"), [("hero", "visual"), ("testimonials", "illustration")])
def test_section_images_are_declared_as_illustrations(key, name):
    section_type = {t.key: t for t in registry.types()}[key]
    field = section_type.Form.base_fields[name]
    assert isinstance(field, Illustration)
    # Sans ratio, les attributs width/height du gabarit mentiraient.
    assert field.ratio is not None


def test_list_item_images_are_declared_as_illustrations():
    types = {t.key: t for t in registry.types()}
    indicator = types["figures"].Form.base_fields["indicators"].item_form
    assert isinstance(indicator.base_fields["image"], Illustration)
    card = types["jobs"].Form.base_fields["cards"].item_form
    assert isinstance(card.base_fields["image"], Illustration)


def _declared_image_paths():
    """Every image path the code declares as a default, read from the
    registry rather than duplicated here as literals — a changed editorial
    photo (a card's picture, say) must not break this test."""
    types = {t.key: t for t in registry.types()}
    paths = [types["hero"].Form.base_fields["visual"].initial]
    paths += [indicator["image"] for indicator in types["figures"].Form.base_fields["indicators"].initial]
    paths.append(types["testimonials"].Form.base_fields["illustration"].initial)
    for key in ("jobs", "services"):
        paths += [card["image"] for card in types[key].Form.base_fields["cards"].initial]
    return paths


def test_the_public_page_still_serves_the_code_images():
    # Compte exact par chemin : un décompte plus lâche laisserait passer une
    # image disparue ou dupliquée. Les chemins eux-mêmes viennent du code, pas
    # d'une liste recopiée ici : changer une photo de carte ne doit pas casser
    # ce test.
    body = Client().get("/").content.decode()
    for path, count in Counter(_declared_image_paths()).items():
        needle = f'src="{settings.STATIC_URL}{path}"'
        assert body.count(needle) == count, path


def _fields_with_ratio():
    """Every declared `Illustration` whose `ratio` is set, as
    `(section_type, field_name, field)` — discovered by walking the registry
    rather than hand-listed, so a new illustrated field is covered
    automatically instead of silently going unchecked."""
    for section_type in registry.types():
        for name, field in section_type.Form.base_fields.items():
            if isinstance(field, ListField):
                for sub_name, sub_field in field.item_form.base_fields.items():
                    if isinstance(sub_field, Illustration) and sub_field.ratio is not None:
                        yield section_type, sub_name, sub_field
            elif isinstance(field, Illustration) and field.ratio is not None:
                yield section_type, name, field


# The search cards carry no `width`/`height`: their shape is enforced in CSS
# by `.carte-media__media { aspect-ratio: 16 / 10 }`, not by HTML attributes —
# there is nothing here for the test below to check, deliberately rather than
# by omission.
NO_RENDERED_DIMENSIONS = {("jobs", "image"), ("services", "image")}


def test_every_ratio_declaring_field_has_matching_rendered_dimensions():
    # Personne ne relie à l'œil un `ratio` en Python aux attributs `width` et
    # `height` d'un gabarit : ce test les compare directement, dans les deux
    # sens, pour chaque champ qui déclare un `ratio` — la liste vient du
    # registre, pas d'une énumération à la main.
    fields = list(_fields_with_ratio())
    checked = set()
    for section_type, field_name, field in fields:
        key = (section_type.key, field_name)
        if key in NO_RENDERED_DIMENSIONS:
            continue
        section = section_type()
        rendered = get_template(section_type.template).render({"content": section.content, "section": section})
        matches = re.findall(r'<img[^>]*width="(\d+)"[^>]*height="(\d+)"', rendered)
        assert matches, f"{section_type.key}.{field_name} a un ratio mais aucune balise <img> dimensionnée"
        ratio_width, ratio_height = field.ratio
        for width, height in matches:
            assert int(width) * ratio_height == int(height) * ratio_width, f"{section_type.key}.{field_name}"
        checked.add(key)
    # Chaque champ à ratio est soit vérifié ci-dessus, soit explicitement
    # excusé : aucun ne doit passer entre les deux silencieusement.
    all_keys = {(section_type.key, field_name) for section_type, field_name, _ in fields}
    assert checked | NO_RENDERED_DIMENSIONS == all_keys


def _rendered(section):
    """Rend le gabarit d'une section, comme `index.html` le fait pour de vrai."""
    return get_template(section.template).render({"content": section.content, "section": section})


def test_hero_never_emits_an_empty_src():
    types = {t.key: t for t in registry.types()}
    section = types["hero"]({"visual": "../../../etc/passwd"})
    assert 'src=""' not in _rendered(section)


def test_figures_never_emits_an_empty_src():
    types = {t.key: t for t in registry.types()}
    Figures = types["figures"]
    indicators = Figures.defaults()["indicators"]
    indicators[0]["image"] = "../../../etc/passwd"
    section = Figures({"indicators": indicators})
    assert 'src=""' not in _rendered(section)


def test_testimonials_never_emits_an_empty_src():
    types = {t.key: t for t in registry.types()}
    section = types["testimonials"]({"illustration": "../../../etc/passwd"})
    assert 'src=""' not in _rendered(section)


def test_search_cards_never_emits_an_empty_src():
    types = {t.key: t for t in registry.types()}
    Jobs = types["jobs"]
    cards = Jobs.defaults()["cards"]
    cards[0]["image"] = "../../../etc/passwd"
    section = Jobs({"cards": cards})
    assert 'src=""' not in _rendered(section)
