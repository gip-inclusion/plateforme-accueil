"""Le champ image : déclaration, provenance, résolution en URL."""

from django import forms

from accueil.sections.base import Credit, Illustration, ListField, Registry, SectionType


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
