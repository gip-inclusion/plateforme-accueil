"""Editing a section through the fields it declares.

A section type already describes its content as a Django form, so the editor is
that form — no per-section code. Two things are added here: a readable widget
for repeatable lists (JSON, which only the admin still needs now that `/edition/`
edits them item by item), and the rule that only *differences* from the code are
stored.

Used by both the admin and `/edition/`.
"""

import copy
import json

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import File

from accueil import uploads
from accueil.models import Section
from accueil.sections import Illustration, ListField


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


class IllustrationWidget(forms.Widget):
    """The current image, and a way to replace it.

    The current path travels in a hidden input: an `<input type="file">` cannot
    carry the existing value, and without it a save that does not change the
    image would erase it.

    Written on `forms.Widget` rather than `ClearableFileInput`: the latter
    brings a clearing protocol and a data-reading behaviour this widget
    replaces entirely, and which would only hide surprises.

    Holds the two facts about *this request*'s posted data that
    `IllustrationEditor.bound_data` needs to decide what to re-render: the
    hidden `_current` value, and the key a successful upload was stored under.
    Both belong here, not on the field, because both are facts about what was
    posted — the widget's domain. Safe to keep on `self`: a widget instance is
    deep-copied per form instance (Django copies `base_fields`, widget
    included, on every `Form()` call), never shared across requests.
    """

    template_name = "edition/widgets/illustration.html"
    # Without this Django does not know the form carrying this field must be
    # `multipart`, and the file never arrives.
    needs_multipart_form = True

    def __init__(self, attrs=None):
        super().__init__(attrs)
        self.posted_current = ""
        self.uploaded_key = None

    def value_from_datadict(self, data, files, name):
        uploaded = files.get(name)
        self.posted_current = data.get(f"{name}_current", "")
        if uploaded is not None:
            return uploaded
        return self.posted_current

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["may_upload"] = settings.UPLOADS_ENABLED
        return context

    def id_for_label(self, id_):
        # With uploads disabled there is no `<input type="file">` to carry
        # this id (see the widget template): a `<label for="…">` pointing at
        # nothing is a dangling reference, so give the label nothing to point
        # at. `edition/section.html` then renders `for=""` — a non-conforming
        # but harmless empty ID reference, not an omitted attribute.
        if not settings.UPLOADS_ENABLED:
            return ""
        return super().id_for_label(id_)

    def use_required_attribute(self, initial):
        # The value lives in the hidden `_current` input, never in the file
        # input itself: an empty file input on save means "keep the current
        # image", not "missing". `forms.Widget`'s default
        # (`not self.is_hidden`) does not know that — unlike `FileInput`,
        # whose own override exists for exactly this reason — so without this
        # a browser's constraint validation would block every save that does
        # not change the image, on `hero` and `testimonials` alike.
        return False


class IllustrationEditor(forms.CharField):
    """Edits an `Illustration`: a posted file becomes a storage key, otherwise
    the current value is kept as it is."""

    widget = IllustrationWidget

    def __init__(self, illustration, **kwargs):
        self.illustration = illustration
        super().__init__(
            required=illustration.required,
            label=illustration.label,
            help_text=illustration.help_text,
            initial=illustration.initial,
            **kwargs,
        )

    def clean(self, value):
        if isinstance(value, File):
            if not settings.UPLOADS_ENABLED:
                # `UPLOADS_ENABLED` (config/settings.py) means durable storage
                # is actually configured; without it, `uploads.store` would
                # still happily write onto disk that vanishes at the next
                # deploy. The UI only offers the file input when this is true
                # (see the widget template), so reaching here means a
                # hand-crafted request — refuse it the same way any other
                # invalid upload is refused.
                raise ValidationError("Le téléversement d'image n'est pas disponible pour le moment.")
            value = uploads.store(value, max_width=self.illustration.max_width, ratio=self.illustration.ratio)
            # Kept on the widget (not returned here) so a re-render after some
            # *other* field on the same form fails validation still shows this
            # upload — see `bound_data`. If the form is never resubmitted
            # successfully, the file stays on storage with nothing pointing
            # at it: an accepted orphan, not addressed by content-hash naming
            # (that only prevents *duplicates*). Deferring the write instead
            # would defeat the point of `bound_data`, the key is unguessable,
            # and the never-delete policy on uploads is deliberate — so this
            # trade-off is kept, not fixed.
            self.widget.uploaded_key = value
        value = super().clean(value)
        # The hidden `<name>_current` input is client-supplied, and its value
        # ends up in a public `src`. The editing UI is staff-only, so this is
        # not a public attack surface, but the same shape check the display
        # filter applies (`accueil/templatetags/illustrations.py`, sharing
        # `accueil.uploads.is_well_shaped_path`) is cheap enough to also apply
        # here, so a mangled value is refused at save time rather than
        # silently rendering nothing later.
        if value and not uploads.is_well_shaped_path(value):
            raise ValidationError("Chemin d'image invalide.")
        return value

    def bound_data(self, data, initial):
        # `BoundField.value()` calls this to decide what the widget re-renders
        # after a failed submission. `data` here is the *raw* widget value
        # (`value_from_datadict` runs again against the same `request.FILES`),
        # so a freshly uploaded file reappears here as the same file object,
        # not as the key `clean` already computed for it.
        if isinstance(data, File):
            # `widget.uploaded_key` is set when *this* field's own upload
            # succeeded: show the new image, even though some other field on
            # the form rejected the submission — the upload is not lost.
            # Otherwise (this field's own file was rejected, e.g. not an
            # image): fall back to what was actually posted as the current
            # value, so the editor still sees the image they had before this
            # attempt, not the field's own hard-coded default.
            return self.widget.uploaded_key or self.widget.posted_current
        return data


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
        # House-theme classes, so the editing UI gets real form controls. The
        # admin ignores them, which is fine — it is on its way out.
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs["class"] = f"form-control {widget.attrs.get('class', '')}".strip()

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
    fields = {}
    for name, declared in section_type.Form.base_fields.items():
        if isinstance(declared, Illustration):
            fields[name] = IllustrationEditor(declared)
        elif isinstance(declared, ListField):
            fields[name] = ListEditor(declared)
        else:
            fields[name] = copy.deepcopy(declared)
    return type("SectionForm", (SectionForm,), {**fields, "section_type": section_type})
