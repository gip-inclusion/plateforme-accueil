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
    """An image on the page.

    The value is a path, and stays text: either a static file declared in the
    code, or the key of an uploaded file (`uploads/…`). This single shape is
    what lets a value be compared to its default, only the deviation stored,
    and a fallback to the code happen without a special case.

    `max_width` is the image's useful width on the page, in pixels: an upload
    wider than that is scaled down to it, a smaller one is never enlarged. The
    rule for choosing it: measure the widest width the image actually renders
    at in the page's CSS across every breakpoint, not just the widest viewport
    — a narrower viewport can still render the image wider, if a column that
    was split becomes single at that width. Never use the HTML `width`
    attribute, which CSS can override, or the source file's own size. Double
    that measured width for dense screens, and round *up* to a tidy number —
    rounding down loses pixels. Name the CSS selector and the measured width
    in a comment next to the declaration, so the number stays checkable
    against the stylesheet rather than becoming folklore.

    `ratio`, when declared, is the `(width, height)` shape an upload is
    cropped to — without it, the `width`/`height` attributes hard-coded in
    the template would lie the moment an editor uploads an image of another
    shape.

    The `illustration` template filter (`accueil/templatetags/illustrations.py`)
    resolves this value to a URL, and returns an empty string when there is
    nothing to show. A template must treat that as *render no image* — guard
    it, never emit `<img src="">` (see CLAUDE.md, section « Iframe »).
    """

    def __init__(self, *, max_width, ratio=None, **kwargs):
        self.max_width = max_width
        self.ratio = ratio
        # Shown to an editor who sees a file picker, not a path field: name
        # what actually happens on save, not the storage detail underneath.
        # True whether this field sits at the top of a section
        # (`hero.visual`, `testimonials.illustration`) or inside a
        # `ListField` item (`figures.Indicator.image`, `search.Card.image`):
        # both are rendered through `IllustrationEditor`, via
        # `section_form_class` and `item_form_class` respectively.
        kwargs.setdefault(
            "help_text",
            "Remplacez l'image en choisissant un fichier. Sans nouveau fichier, l'image actuelle est conservée.",
        )
        super().__init__(**kwargs)


CREDIT_SUFFIX = "_credit"  # appended to an illustration's name to name its credit field


class Credit(forms.CharField):
    """Provenance or licence of an uploaded image.

    Optional, and never shown on the public page: it is a note for the team.
    A distinct type so the item previews in `/edition/` can leave it out of
    displayed content, and so it stands out at a glance in a declaration.
    """


def add_credit_fields(form_class):
    """Give each `Illustration` on the form its provenance field.

    Injected rather than declared: a compliance field a section could forget
    to write would be forgotten. Called when a section type registers and
    when a `ListField` is built, so repeated items get one too. Names each
    field after `CREDIT_SUFFIX` and records the illustration it belongs to on
    `illustration_name`, so downstream code asks the field for its pairing
    rather than parsing its name.

    Rebuilds `base_fields` rather than appending, so each credit field sits
    right after the illustration it describes — moving a hand-declared credit
    there too rather than leaving it trailing, though its identity is kept,
    never duplicated or replaced. Idempotent: a repeated call finds every
    credit field already in place and changes nothing.

    Also rebinds `declared_fields`, which Django's metaclass sets to the same
    dict object at class creation: a subclass's own fields are collected from
    its bases' `declared_fields`, not their `base_fields`, so leaving it
    stale would silently drop the injected fields from any subclass.
    """
    fields = form_class.base_fields
    rebuilt = {}
    for name, field in fields.items():
        rebuilt[name] = field
        if not isinstance(field, Illustration):
            continue
        credit_name = f"{name}{CREDIT_SUFFIX}"
        if credit_name in fields:
            rebuilt[credit_name] = fields[credit_name]
            continue
        credit = Credit(
            label=f"Provenance de « {field.label} »" if field.label else "Provenance de l'image",
            required=False,
            initial="",
            help_text="Origine ou licence de l'image. Pour l'équipe : jamais affiché sur la page.",
        )
        credit.illustration_name = name
        rebuilt[credit_name] = credit
    form_class.base_fields = rebuilt
    form_class.declared_fields = rebuilt


class ListField(forms.Field):
    """A repeatable block, stored as a list of dictionaries.

    Each item is validated by an ordinary Django form, so a card or a shortcut
    declares its fields exactly like a section does. `/edition/` edits a
    top-level list item by item, on a board; a list nested *inside* an item is
    still edited as JSON, and the validation here is what keeps that honest.

    Construction is not side-effect free: it permanently adds credit fields to
    `item_form`, the class the caller passed in.
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
        # `/edition/`'s own board edits a top-level list item by item, with
        # no JSON in sight — but a `ListField` nested *inside* an item
        # (`profiles.Profile.steps`) still goes through `ListEditor`
        # (`accueil/forms.py`) as raw JSON, on the one screen whose whole
        # premise is that an editor no longer writes JSON. Without a default
        # help text that textarea would carry none at all.
        kwargs.setdefault("help_text", "Liste au format JSON : un tableau d'objets, un par élément.")
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
                # The label ("Identifiant"), never `self.unique` ("slug"):
                # identifiers are English precisely because an editor never
                # reads them (CLAUDE.md).
                label = self.item_form.base_fields[self.unique].label or self.unique
                raise ValidationError(f"Le champ « {label} » doit être différent pour chaque élément.")
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
