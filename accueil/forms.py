"""Editing a section through the fields it declares.

A section type already describes its content as a Django form, so the editor is
that form — no per-section code. Two things are added here: a readable widget
for repeatable lists (JSON, until `/pilotage/` gives them a real one), and the
rule that only *differences* from the code are stored.

Used by the admin today, and by `/pilotage/` when it lands.
"""

import copy
import json

from django import forms
from django.core.exceptions import ValidationError

from accueil.models import Section
from accueil.sections import ListField


class JsonWidget(forms.Textarea):
    """Shows a list of items as indented JSON rather than a Python repr."""

    def __init__(self, attrs=None):
        super().__init__({"rows": 12, "class": "vLargeTextField", **(attrs or {})})

    def format_value(self, value):
        if value in (None, ""):
            return ""
        if isinstance(value, str):
            return value  # a failed submission: give the text back untouched
        return json.dumps(value, ensure_ascii=False, indent=2)


class ListEditor(forms.CharField):
    """Edits a `ListField` as JSON, then validates it as the list it is."""

    def __init__(self, list_field, **kwargs):
        self.list_field = list_field
        super().__init__(
            widget=JsonWidget,
            required=list_field.required,
            label=list_field.label,
            help_text=list_field.help_text,
            **kwargs,
        )

    def clean(self, value):
        if isinstance(value, str):
            try:
                value = json.loads(value or "[]")
            except json.JSONDecodeError as erreur:
                raise ValidationError(f"JSON invalide : {erreur.msg} (ligne {erreur.lineno}).") from erreur
        return self.list_field.clean(value)


class SectionForm(forms.ModelForm):
    """The section's own fields, plus the content it declares.

    Only the values that differ from the code are written back, so a wording
    changed in a pull request still reaches the page — unless an editor
    deliberately overrode that very field.
    """

    section_type = None  # set by `section_form_class`

    class Meta:
        model = Section
        fields = ("position", "active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.section_type is None or not self.instance.pk:
            return
        # Seed each field with what the page currently shows: the code default,
        # or the override if there is one.
        merged = self.section_type(self.instance.content).content
        for name in self.section_type.Form.base_fields:
            self.fields[name].initial = merged.get(name)

    def clean(self):
        cleaned = super().clean()
        if self.section_type is None:
            return cleaned
        defaults = self.section_type.defaults()
        # Store the differences only. Comparing the cleaned value against the
        # default is what keeps `content` empty for untouched sections, so a
        # wording changed in a pull request still reaches the page.
        self.instance.content = {
            name: cleaned[name]
            for name in self.section_type.Form.base_fields
            if name in cleaned and cleaned[name] != defaults[name]
        }
        return cleaned


def section_form_class(section_type):
    """A form for one section type, with its declared fields as real fields.

    Built as a class rather than added per instance: the admin reads
    `base_fields` off the class to decide what to render.
    """
    fields = {
        name: (ListEditor(declared) if isinstance(declared, ListField) else copy.deepcopy(declared))
        for name, declared in section_type.Form.base_fields.items()
    }
    return type("SectionForm", (SectionForm,), {**fields, "section_type": section_type})
