"""Resolving a platform-relative path to a URL.

Sections declare where a link goes as a path (`/search/employers/results`), not
as an absolute URL: which deployment serves it is not content, it is where the
page happens to be embedded. This tag decides the origin, the same way
`illustration` decides an image's prefix.

A tag rather than a filter because the answer depends on the request — see
`accueil/platform_urls.py`.
"""

from django import template

from accueil import platform_urls


register = template.Library()


@register.simple_tag(takes_context=True)
def platform_url(context, path):
    # A section that has no target renders no link: returning the bare origin
    # would send the visitor to the platform home for no reason.
    if not path:
        return ""
    return platform_urls.url(context.get("request"), path)
