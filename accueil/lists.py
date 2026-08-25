"""Reading and writing one section's repeatable list — no HTTP in here.

A `ListField` (declared alongside a section's other fields, see
`accueil.sections.base`) is what an item screen under `/edition/` reads and
writes through. Everything here is request-free: it raises `Http404` rather
than redirect, on the same three ways a URL segment can be wrong (an unknown
section, a kind no longer in the code, a name that isn't a declared list) —
`accueil.editing` wraps these in a view, never the other way round.
"""

import copy
import hashlib
import json

from django.core.exceptions import ValidationError
from django.http import Http404

from accueil.sections import ListField


def _list_field(section_type, name):
    """The declared `ListField` for `name`, or a 404.

    A missing or mistyped `name` only ever reaches here from a URL segment
    (Tasks 9–11), so it is the caller's routing that is wrong, not the data —
    the same lens `get_object_or_404` applies to a bad primary key. Without
    this, a name that exists but names some other kind of field (`"title"`)
    would still reach `Field.clean`, which happily stringifies a list into
    `"['a', 'b']"` and lets it through: nothing downstream would catch that
    before it lands in the database.
    """
    field = section_type.Form.base_fields.get(name)
    if not isinstance(field, ListField):
        raise Http404(f"« {name} » n'est pas une liste déclarée sur « {section_type.key} ».")
    return field


def list_values(row, section_type, name, field=None):
    """The list as it renders: the override if there is one, else the code.

    `field` lets a caller that already resolved it through `_list_context`
    pass it straight in, rather than have `_list_field` look it up again.

    Known limitation, deliberately left unaddressed here: `SectionType.__init__`
    swallows a per-field `ValidationError` and falls back to the code default
    when an override no longer validates (a rule tightened after the override
    was written, say). That is the right behaviour for the public page, but on
    an editing screen it means an editor is shown the code's content in place
    of their own unreadable override, with nothing to say so. `_apply` (and
    `item`/`item_add`) guard against this with `_override_is_unreadable`
    before ever calling this function to mutate anything; a bare read through
    this helper (the section screen's own display, say) still shows the
    code's content silently, which remains an `accueil.editing` concern, not
    this one.
    """
    field = field or _list_field(section_type, name)  # 404 on a bad name, before touching row.content
    row_content = row.content if isinstance(row.content, dict) else {}
    return copy.deepcopy(section_type(row_content).content[name])


def save_list(row, section_type, name, values, field=None):
    """Validate a list whole, then write it back. Returns the cleaned list.

    `field` lets a caller that already resolved it through `_list_context`
    pass it straight in, rather than have `_list_field` look it up again.

    Validating the whole list on every write — not just the touched item — is
    what makes `min_num`, `max_num` and `unique` hold: removing the last
    indicator must be refused, not accepted.

    Returns `cleaned`, not `values`: cleaning can change the shape (an
    injected `..._credit` key, a coerced integer), so a caller that chains a
    second operation must carry on from what was actually stored, not from
    what it originally passed in.

    Last-write-wins: this writes the whole `content` column, so a concurrent
    edit — of this list or of any other field on the same section — made
    between this row being loaded and this save is silently overwritten. That
    was already true of the section form this replaces; the repeater turns
    every add, duplicate, move and delete into its own full-column write,
    which multiplies the exposure but does not change its nature. Acceptable
    for a small editorial team working one section at a time; revisit if that
    stops being true.
    """
    field = field or _list_field(section_type, name)
    if not isinstance(row.content, dict):
        row.content = {}
    cleaned = field.clean(values)
    if cleaned == field.clean(copy.deepcopy(field.initial)):
        # Back to the code's own values: the override no longer has a reason
        # to exist, and the section follows pull requests again.
        row.content.pop(name, None)
    else:
        row.content[name] = cleaned
    row.save(update_fields=["content"])
    return cleaned


def _override_is_unreadable(row, section_type, name):
    """True when `row.content` holds an override for `name` that no longer
    validates, and `SectionType.__init__` has silently fallen back to the
    code default for it (see the limitation documented on `list_values`).

    Acting on such a list would be destructive: `list_values` would hand
    back the code's own items, an item operation would mutate those, and
    `save_list` would write them back as if they were the editor's, erasing
    whatever they had actually written with no message and nothing left to
    recover. `accueil.editing` calls this first and refuses the operation
    instead, on every screen that could mutate a list.
    """
    row_content = row.content if isinstance(row.content, dict) else {}
    if name not in row_content:
        return False
    try:
        section_type.clean_value(name, row_content[name])
    except ValidationError:
        return True
    return False


def _digest(values):
    """A short fingerprint of a list's cleaned content.

    Carried on the POST as an optimistic-concurrency token: the screen that
    renders the list embeds the digest of the list as it was read, and the
    view refuses the operation rather than apply it if the list has changed
    underneath since — the only signal available for a list whose items were
    deliberately left without a stored identity.
    """
    payload = json.dumps(values, sort_keys=True, default=str).encode()
    return hashlib.sha256(payload).hexdigest()[:16]
