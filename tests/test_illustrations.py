"""Le champ image : déclaration, provenance, résolution en URL."""

import copy

from django import forms

from accueil.sections.base import Credit, Illustration, ListField, Registry, SectionType, add_credit_fields


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
