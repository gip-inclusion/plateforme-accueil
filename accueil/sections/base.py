"""Section registry: what the page is made of, and in which order.

A section type declares three things — a key, a template, and a Django form
whose ``initial`` values are the default content. Nothing is persisted by
default: the page renders those defaults, which live in the code and are
reviewed like any other change.

Only an editor's *overrides* are stored, and merged over these defaults at
render time. Opening a new field to editing therefore costs one form field and
one template variable — no migration, no data backfill.

See CLAUDE.md, section « Sections », for the authoring contract.
"""

import copy

from django import forms
from django.core.exceptions import ValidationError


def check_shape(field, value):
    """Reject a value of the wrong kind before a form stringifies it.

    `CharField.to_python` turns anything into text, so without this a list or a
    number lands on the page as "[…]" or "42".
    """
    if isinstance(field, ListField):
        expected, ok = "une liste", isinstance(value, list)
    elif isinstance(field, forms.IntegerField):
        expected, ok = "un nombre entier", isinstance(value, int) and not isinstance(value, bool)
    else:
        expected, ok = "du texte", isinstance(value, str)
    if not ok:
        raise ValidationError(f"Cette valeur doit être {expected}.")


class Reference(forms.SlugField):
    """An identifier the page consumes but never displays — a feed id, or a
    slug tying a tab to its panel. Slug-shaped on purpose: several of these end
    up in HTML ids, where a space would silently break `aria-controls`."""


class Illustration(forms.CharField):
    """Une image de la page.

    La valeur est un chemin, et reste du texte : soit un fichier statique
    déclaré dans le code, soit la clé d'un fichier téléversé (`uploads/…`).
    Cette forme unique est ce qui permet de comparer au défaut, de ne stocker
    que les écarts et de revenir au code sans cas particulier.

    `max_width` est la largeur utile de l'image sur la page, en pixels ; un
    téléversement plus large y est ramené, un plus petit n'est jamais agrandi.
    `ratio`, quand il est déclaré, est le format `(largeur, hauteur)` auquel
    un téléversement est recadré — sans lui, les attributs `width`/`height`
    codés dans le gabarit mentiraient dès qu'un rédacteur envoie une image
    d'un autre format.
    """

    def __init__(self, *, max_width, ratio=None, **kwargs):
        self.max_width = max_width
        self.ratio = ratio
        super().__init__(**kwargs)


class Credit(forms.CharField):
    """Provenance ou licence d'une image téléversée.

    Facultatif, jamais affiché sur la page : c'est une note pour l'équipe.
    Ce type distinct existe pour que la planche d'aperçus puisse l'écarter du
    contenu, et pour qu'il se repère d'un coup d'œil dans une déclaration.
    """


def add_credit_fields(form_class):
    """Donne à chaque `Illustration` du formulaire son champ de provenance.

    Injecté plutôt que déclaré : un champ de conformité qu'on peut oublier
    d'écrire serait oublié. Appelé à l'enregistrement d'un type de section et
    à la construction d'un `ListField`, donc les éléments répétés l'ont aussi.
    """
    for name, field in list(form_class.base_fields.items()):
        if not isinstance(field, Illustration):
            continue
        if f"{name}_credit" in form_class.base_fields:
            continue
        form_class.base_fields[f"{name}_credit"] = Credit(
            label=f"Provenance de « {field.label or name} »",
            required=False,
            initial="",
            help_text="Origine ou licence de l'image. Pour l'équipe : jamais affiché sur la page.",
        )
    return form_class


class ListField(forms.Field):
    """A repeatable block, stored as a list of dictionaries.

    Each item is validated by an ordinary Django form, so a card or a shortcut
    declares its fields exactly like a section does. The editing UI for these
    is still to come; until then they are edited as JSON, and the validation
    here is what keeps that honest.
    """

    def __init__(self, item_form, *, min_num=0, max_num=None, unique=None, **kwargs):
        self.item_form = item_form
        add_credit_fields(item_form)
        self.min_num = min_num
        self.max_num = max_num
        self.unique = unique  # name of a key that must not repeat across items
        # A list with a minimum is required by definition; deriving it keeps a
        # declaration from contradicting itself.
        kwargs["required"] = min_num > 0
        super().__init__(**kwargs)

    def item_defaults(self):
        return {name: field.initial for name, field in self.item_form.base_fields.items() if field.initial is not None}

    def clean(self, value):
        if value is None or value == "":
            value = []
        if not isinstance(value, list):
            raise ValidationError("Cette valeur doit être une liste.")
        if len(value) < self.min_num:
            raise ValidationError(f"Il faut au moins {self.min_num} élément(s).")
        if self.max_num is not None and len(value) > self.max_num:
            raise ValidationError(f"Il faut au plus {self.max_num} élément(s).")

        nettoyes = []
        for rang, item in enumerate(value, start=1):
            if not isinstance(item, dict):
                raise ValidationError(f"L'élément {rang} doit être un objet.")
            for name, sub_field in self.item_form.base_fields.items():
                if name in item:
                    try:
                        check_shape(sub_field, item[name])
                    except ValidationError as erreur:
                        raise ValidationError(f"Élément {rang}, {name} : {erreur.messages[0]}") from erreur
            # Merged under the item so that an omitted key falls back to the
            # child form's own default, as it does for a section.
            formulaire = self.item_form({**self.item_defaults(), **item})
            if not formulaire.is_valid():
                premier = next(iter(formulaire.errors.values()))[0]
                raise ValidationError(f"Élément {rang} : {premier}")
            nettoyes.append(formulaire.cleaned_data)

        if self.unique:
            valeurs = [item.get(self.unique) for item in nettoyes]
            if len(set(valeurs)) != len(valeurs):
                raise ValidationError(f"Le champ « {self.unique} » doit être différent pour chaque élément.")
        return nettoyes


class SectionType:
    """Base class for a section. Subclass, set the four attributes, register."""

    key = ""  # stable identifier, also the database key
    label = ""  # human name, shown in the future editing UI
    position = 0  # place in the page, spaced by 10 so inserting is cheap
    template = ""
    anchor = ""  # the section's HTML id, used as a page anchor
    modifiers = ""  # extra CSS classes on the <section>

    class Form(forms.Form):
        """Editable fields. Empty means nothing is editable yet — and that is a
        perfectly good steady state for copy that changes once a year."""

    def __init__(self, overrides=None):
        defaults = self.defaults()
        # Anything malformed is dropped rather than raised: the page has to
        # render whatever ended up in the database.
        if not isinstance(overrides, dict):
            overrides = {}
        # Unknown keys are ignored rather than rendered: a field removed from
        # the form must not resurrect stale content.
        self.stale_keys = sorted(key for key in overrides if key not in defaults)

        kept = {}
        for name, value in overrides.items():
            if name not in defaults:
                continue
            try:
                kept[name] = self.clean_value(name, value)
            except ValidationError:
                continue  # unusable override -> the text from the code
        self.content = defaults | kept

    @classmethod
    def clean_value(cls, name, value):
        """Validate one override against the field that declares it."""
        field = cls.Form.base_fields[name]
        check_shape(field, value)
        return field.clean(value)

    @classmethod
    def defaults(cls):
        # Copied: `initial` on a list field is a mutable class attribute, and a
        # section must never be able to mutate it for the whole process.
        return {name: copy.deepcopy(field.initial) for name, field in cls.Form.base_fields.items()}

    def __repr__(self):
        return f"<{type(self).__name__} {self.key}>"


class Registry:
    def __init__(self):
        self._types = {}

    def register(self, cls):
        if not cls.key or not cls.template:
            raise ValueError(f"{cls.__name__} doit définir `key` et `template`")
        if cls.key in self._types:
            raise ValueError(f"clé de section déjà enregistrée : {cls.key}")
        add_credit_fields(cls.Form)
        self._types[cls.key] = cls
        return cls

    def types(self):
        return sorted(self._types.values(), key=lambda cls: cls.position)

    def sections(self, overrides=None):
        """Instantiate every section, in order. `overrides` maps a section key
        to the values an editor changed for it."""
        overrides = overrides or {}
        return [cls(overrides.get(cls.key)) for cls in self.types()]


registry = Registry()
