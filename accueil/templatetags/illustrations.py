"""Resolving an illustration path to a URL.

An `Illustration` value has two shapes — a static file from the code, or an
upload key — and templates have no business knowing which one they hold: this
filter decides on the prefix. It replaces `{% static %}` everywhere an image is
content rather than chrome.

An empty return means *render no image*: a caller must guard rather than emit
`<img src="">`, which the HTML spec resolves against the document URL — a
duplicated page load, since this page lives in an iframe on a public site.
"""

import logging

from django import template
from django.core.files.storage import storages
from django.templatetags.static import static

from accueil.sections.base import UPLOAD_PREFIX


register = template.Library()
logger = logging.getLogger(__name__)


@register.filter
def illustration(path):
    if not path or not isinstance(path, str) or ".." in path:
        return ""
    if path.startswith(UPLOAD_PREFIX):
        try:
            # Goes through the storage rather than concatenating a URL, so the
            # same code works on local disk and on the bucket. `storages["default"]`
            # is instantiated lazily, right here at render time: a missing or
            # malformed bucket setting must not 500 the public page over a missing
            # image. The page matters more than the picture — but log it, since
            # otherwise every uploaded image silently vanishes with no signal.
            return storages["default"].url(path)
        except Exception:
            logger.exception("Failed to resolve illustration upload URL for %r", path)
            return ""
    # A static path is a fact declared in the code: a mistyped path is a bug
    # and should raise loudly here, where a reviewer or CI would catch it,
    # rather than be swallowed like an environmental storage failure.
    return static(path)
