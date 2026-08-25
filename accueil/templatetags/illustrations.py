"""Resolving an illustration path to a URL.

An `Illustration` value has two shapes — a static file from the code, or an
upload key — and templates have no business knowing which one they hold: this
filter decides on the prefix. It replaces `{% static %}` everywhere an image is
content rather than chrome.
"""

from django import template
from django.core.files.storage import storages
from django.templatetags.static import static


register = template.Library()

# Everything uploaded lives under this prefix; it is what tells a storage key
# apart from a static file path.
UPLOAD_PREFIX = "uploads/"


@register.filter
def illustration(path):
    if not path:
        return ""
    if path.startswith(UPLOAD_PREFIX):
        # Goes through the storage rather than concatenating a URL, so the same
        # code works on local disk and on the bucket.
        return storages["default"].url(path)
    return static(path)
