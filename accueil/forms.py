"""Editing a section through the fields it declares.

A section type already describes its content as a Django form, so the editor is
that form — no per-section code. Two things are added here: a readable JSON
widget for repeatable lists — which the admin still needs for every list, and
`/edition/` only for a list nested inside an item, its own board handling the
rest — and the rule that only *differences* from the code are stored.

Used by both the admin and `/edition/`.
"""

import copy
import json

from django import forms
from django.conf import settings
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
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
        # `illustration.help_text` ("Remplacez l'image en choisissant un
        # fichier…") tells an editor to do exactly what the widget template
        # says is unavailable, right below it, when uploads are not
        # configured — the widget's own sentence already covers that case,
        # so this one steps aside rather than contradict it.
        help_text = illustration.help_text if settings.UPLOADS_ENABLED else ""
        super().__init__(
            required=illustration.required,
            label=illustration.label,
            help_text=help_text,
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


def _map_editable_fields(base_fields):
    """Map a form's declared fields to their editing widgets.

    Shared by `section_form_class` and `item_form_class`, which used to carry
    byte-identical copies of this loop: an `Illustration` becomes a real file
    picker (`IllustrationEditor`), a `ListField` — top-level or nested inside
    an item, `profiles.Profile.steps` — becomes a `ListEditor` (raw JSON;
    there is no item-by-item editor for a nested repeater), and anything else
    is deep-copied untouched, so the two callers never share a mutable field
    instance.
    """
    fields = {}
    for name, declared in base_fields.items():
        if isinstance(declared, Illustration):
            fields[name] = IllustrationEditor(declared)
        elif isinstance(declared, ListField):
            fields[name] = ListEditor(declared)
        else:
            fields[name] = copy.deepcopy(declared)
    return fields


def _apply_house_classes(fields, *, skip_illustration=False):
    """House-theme widget classes, so the editing UI gets real form controls.

    Shared by `SectionForm.__init__` and `item_form_class`'s `ItemForm`,
    which used to carry two copies of this loop (the admin ignores these
    classes, which is fine — it is on its way out).

    `skip_illustration` differs between the two, deliberately, rather than
    being unified away: `SectionForm` has long applied `form-control` to
    `IllustrationWidget`'s file input too (see
    `test_the_rendered_input_carries_the_widgets_full_attrs`, guarding that
    exact behaviour), while `item_form_class`'s `ItemForm` skips it — its own
    template already carries its styling, and these classes would otherwise
    land on a control that isn't the point of contact a form-control class is
    meant for there.
    """
    for field in fields.values():
        widget = field.widget
        if skip_illustration and isinstance(widget, IllustrationWidget):
            continue
        if isinstance(widget, forms.CheckboxInput):
            widget.attrs.setdefault("class", "form-check-input")
        elif isinstance(widget, forms.Select):
            widget.attrs.setdefault("class", "form-select")
        else:
            widget.attrs["class"] = f"form-control {widget.attrs.get('class', '')}".strip()


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
        _apply_house_classes(self.fields)

        if self.section_type is None or not self.instance.pk:
            return
        # Seed each field with what the page currently shows: the code default,
        # or the override if there is one.
        merged = self.section_type(self.instance.content).content
        for name in self.section_type.Form.base_fields:
            # A declared field this particular form does not carry — every
            # `ListField`, once `section_form_class` is built with
            # `with_lists=False` — is seeded by nothing here: its content
            # stays whatever `SectionForm.clean` preserves from
            # `self.instance.content` untouched.
            if name in self.fields:
                self.fields[name].initial = merged.get(name)

    def clean(self):
        cleaned = super().clean()
        if self.section_type is None:
            return cleaned
        defaults = self.section_type.defaults()
        # What the form does not show, it does not decide — but only if the
        # code still declares it. A field the code still declares but this
        # form does not carry keeps its override untouched: since Task 11
        # (which builds this form with `with_lists=False` for `/edition/`'s
        # section screen), this is what stops saving a section's other
        # fields from wiping its list overrides — every `ListField` reaches
        # here through this branch, not the one below. A key the code no
        # longer declares at all is dropped, as it always was: `Section.clean`
        # (accueil/models.py) rejects an undeclared key at every save, so
        # keeping it here would 500 the editing screen for any section still
        # carrying one.
        content = {
            name: value
            for name, value in self.instance.content.items()
            if name not in self.fields and name in self.section_type.Form.base_fields
        }
        # For the rest, store only the differences. Comparing against the
        # default is what keeps `content` empty on an untouched section, and so
        # what lets a wording changed in a pull request reach the page. The
        # default is cleaned through the same declared field before the
        # comparison, not compared raw: cleaning a `ListField` can change its
        # shape (e.g. `figures.indicators` gains an `image_credit: ""` on
        # every item), so comparing `cleaned[name]` — already shaped that way
        # — against the raw, un-shaped default would never match, and saving
        # a section with nothing actually changed would record a spurious
        # override that then stops following the code.
        cleaned_defaults = {
            name: self.section_type.Form.base_fields[name].clean(copy.deepcopy(defaults[name]))
            for name in self.section_type.Form.base_fields
            if name in cleaned
        }
        content |= {
            name: cleaned[name]
            for name in self.section_type.Form.base_fields
            if name in cleaned and cleaned[name] != cleaned_defaults[name]
        }
        self.instance.content = content
        return cleaned

    def _update_errors(self, errors):
        # `clean()` above preserves a field the code still declares but this
        # form does not carry (every `ListField`, once built with
        # `with_lists=False`) untouched in `self.instance.content` — including
        # when that preserved value is an override that no longer validates
        # (`accueil.lists._override_is_unreadable`'s case). `_post_clean`
        # then runs `self.instance.full_clean()`, and `Section.clean` (the
        # model) rejects that content, keyed on `"content"` — a column no
        # field on *this* form carries. Django's own `_update_errors` cannot
        # attach an error to a field the form does not have and raises
        # `ValueError` instead of the `ValidationError` it is meant to
        # surface. Before Task 7, an unreadable override was silently
        # overwritten by the code's own content, since the whole form
        # validated; before this fix, Task 11 traded that for a 500 on
        # every save of a section carrying one — a more honest failure, but
        # still not a legible one. Any field-keyed error this form cannot
        # carry is folded into the form-wide error list instead.
        if hasattr(errors, "error_dict"):
            merged = {}
            for field, messages in errors.error_dict.items():
                key = field if field in self.fields or field == NON_FIELD_ERRORS else NON_FIELD_ERRORS
                merged.setdefault(key, []).extend(messages)
            errors = ValidationError(merged)
        super()._update_errors(errors)


def item_form_class(list_field):
    """A form for one item of a `ListField`.

    Built from `list_field.item_form.base_fields`, mapped the same way
    `section_form_class` maps a section's own fields — see
    `_map_editable_fields`. Note the mapping is applied to `base_fields`
    directly: this `ItemForm` does not subclass `list_field.item_form`, so a
    `clean()` declared on an item form (`Quote`, `Card`, `Profile`…) would
    never run on this screen. No item form declares one today, and
    `section_form_class` has the same shape (it does not subclass the
    section's `Form` either) — consistent rather than new, and left as a
    known state rather than fixed here.
    """
    fields = _map_editable_fields(list_field.item_form.base_fields)

    class ItemForm(forms.Form):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            _apply_house_classes(self.fields, skip_illustration=True)

    ItemForm.base_fields = fields
    ItemForm.declared_fields = fields
    return ItemForm


def section_form_class(section_type, with_lists=True):
    """A form for one section type, with its declared fields as real fields.

    Built as a class rather than added per instance: the admin reads
    `base_fields` off the class to decide what to render.

    `with_lists=False` leaves every `ListField` out of the generated form —
    `accueil.editing`'s section screen uses this, since its lists are edited
    item by item on their own board (`accueil.previews.section_lists`), not
    as a field on this form. The admin keeps the default: it has no board of
    its own, and still edits a list as raw JSON through `ListEditor`.
    """
    fields = _map_editable_fields(section_type.Form.base_fields)
    if not with_lists:
        fields = {name: field for name, field in fields.items() if not isinstance(field, ListEditor)}
    return type("SectionForm", (SectionForm,), {**fields, "section_type": section_type})
