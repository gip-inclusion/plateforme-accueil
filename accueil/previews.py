"""Turning a list's declared fields into what the editing board shows.

Request-free, like `accueil.lists`: everything here works from a section
type's declaration and content it has already resolved, with no HTTP, no
row, no database. `accueil.editing` calls `section_lists` to build the
preview board on the section screen.

Whether a list's *stored* override is unreadable (see
`accueil.lists._override_is_unreadable`) is a request-level judgment that
stays out of this module on purpose: `content` here is trusted to already be
what should be shown, or not shown at all — `accueil.editing` decides which,
before ever calling `section_lists`.
"""

from django import forms

from accueil.lists import _digest
from accueil.sections import Credit, Illustration, ListField, Reference


def item_parts(list_field, item):
    """Decompose one item into what its card shows, in declaration order.

    Follows the table settled with the project owner: an `Illustration`
    becomes the thumbnail, the first short text field becomes the card's
    title, a field whose widget is a `Textarea` becomes a paragraph shown in
    full, the remaining short fields become `label: value` details, a
    `Reference` or an `IntegerField` becomes a setting shown at the bottom,
    and a `Credit` never appears — it is an internal provenance note, not
    content.
    """
    image = None
    title = None
    paragraphs = []
    details = []
    settings = []
    for name, field in list_field.item_form.base_fields.items():
        if isinstance(field, Credit):
            continue
        value = item.get(name)
        if isinstance(field, Illustration):
            image = value
        elif isinstance(field, (Reference, forms.IntegerField)):
            settings.append((field.label, value))
        elif isinstance(field.widget, forms.Textarea):
            paragraphs.append(value)
        elif title is None:
            title = value
        else:
            details.append((field.label, value))
    return {
        "image": image,
        "title": title,
        "paragraphs": paragraphs,
        "details": details,
        "settings": settings,
    }


def section_lists(section_type, content):
    """The section's lists, decomposed for the preview board.

    `content` is the section's already-resolved content
    (`SectionType(...).content`): the code default for a list an editor
    never touched, its override otherwise.

    Each entry carries the field's name (the template builds the item
    operations' URLs from it), its label, its items — each decomposed by
    `item_parts` and numbered, so the template can withhold the move button
    at either end (`index == 0`, `last`) — a `token`, the same digest
    `accueil.lists._digest` computes for that list's operations, and whether
    adding or deleting is allowed right now, from the field's
    `min_num`/`max_num`.
    """
    boards = []
    for name, field in section_type.Form.base_fields.items():
        if not isinstance(field, ListField):
            continue
        values = content.get(name) or []
        items = [
            {"index": index, "last": index == len(values) - 1, **item_parts(field, item)}
            for index, item in enumerate(values)
        ]
        boards.append(
            {
                "name": name,
                "label": field.label,
                "items": items,
                "token": _digest(values),
                "can_add": field.max_num is None or len(values) < field.max_num,
                "can_delete": len(values) > field.min_num,
            }
        )
    return boards
