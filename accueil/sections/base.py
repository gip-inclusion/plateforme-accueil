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

from django import forms


class SectionType:
    """Base class for a section. Subclass, set the four attributes, register."""

    key = ""  # stable identifier, also the template name and the database key
    label = ""  # human name, shown in the future editing UI
    position = 0  # place in the page, spaced by 10 so inserting is cheap
    template = ""

    class Form(forms.Form):
        """Editable fields. Empty means nothing is editable yet — and that is a
        perfectly good steady state for copy that changes once a year."""

    def __init__(self, overrides=None):
        defaults = self.defaults()
        overrides = overrides or {}
        # Unknown keys are ignored rather than rendered: a field removed from
        # the form must not resurrect stale content.
        self.content = defaults | {key: value for key, value in overrides.items() if key in defaults}
        self.stale_keys = sorted(key for key in overrides if key not in defaults)

    @classmethod
    def defaults(cls):
        return {name: field.initial for name, field in cls.Form.base_fields.items()}

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
