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


# A field named one of these holds the item's own name, whichever position it
# is declared at — checked in this order, so a form that declares both (it
# never does today) picks `title` first. Preferred over "the first short
# field", which promotes whatever happens to be declared first: several item
# forms (`advisors.Tag`, `features.Step`, `profiles.Profile`) declare `icon`
# before their real name, and an icon (`ri-home-smile-2-line`) is never a
# title. Checked over the *name* Python identifiers actually use across this
# codebase (CLAUDE.md: identifiers are English, and consistent), not a
# per-section special case.
TITLE_FIELD_NAMES = ("title", "label")


def item_parts(list_field, item):
    """Decompose one item into what its card shows, in declaration order.

    Follows the table settled with the project owner: an `Illustration`
    becomes the thumbnail, a field named like a title (`TITLE_FIELD_NAMES`)
    becomes the card's title — falling back to the first remaining short
    field, but never to `icon`, which never names the item — a field whose
    widget is a `Textarea` becomes a paragraph shown in full, a nested
    `ListField` (`profiles.Profile.steps`) becomes a count rather than a raw
    dump of dicts, the remaining short fields become `label: value` details,
    a `Reference` or an `IntegerField` becomes a setting shown at the
    bottom, and a `Credit` never appears — it is an internal provenance
    note, not content. An empty optional value (`role=""`, say) is left out
    of `details`/`settings` entirely, rather than shown as a dangling label.
    """
    image = None
    candidates = []  # (name, field, value), in declaration order
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
            if value not in (None, ""):
                settings.append((field.label, value))
        elif isinstance(field, ListField):
            details.append((field.label, f"{len(value or [])} élément(s)"))
        elif isinstance(field.widget, forms.Textarea):
            paragraphs.append(value)
        else:
            candidates.append((name, field, value))

    title = None
    title_index = None
    for wanted in TITLE_FIELD_NAMES:
        for index, (name, field, value) in enumerate(candidates):
            if name == wanted:
                title, title_index = value, index
                break
        if title_index is not None:
            break
    if title_index is None:
        for index, (name, field, value) in enumerate(candidates):
            if name != "icon":
                title, title_index = value, index
                break
    if title_index is not None:
        del candidates[title_index]

    for name, field, value in candidates:
        if value not in (None, ""):
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
    `min_num`/`max_num`. `can_add` does not know about upload availability
    (`accueil.editing._blocks_creation_without_uploads`): that is a
    deployment fact, not something a declaration can answer, so the caller
    narrows it further.
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
