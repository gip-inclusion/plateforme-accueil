"""Which deployment of the platform this page sends its visitors to.

The page is embedded by several environments — production, demo, a throwaway
review app — and there is only one deployment of it. So the destination cannot
be baked into the code: a visitor on the demo site who searches must land on
the demo site, not be thrown to production.

The host says who it is, in the iframe `src`:

    <iframe src="https://…/?host=demo.plateforme.inclusion.gouv.fr">

Read at render time, so every link on the page is already right on first paint
and the whole thing works with no JavaScript.

Security: `host` is a hostname, never a URL, and it is only ever *compared*
against the patterns below — never concatenated into one. An unknown value
falls back to `DEFAULT_ORIGIN`. Building the target from the request instead
would make this an open redirect, and the page is linked from gouv.fr domains.
"""

import re
from fnmatch import fnmatchcase

from django.conf import settings


# A hostname, and a port only for local development. No scheme, no path, no
# credentials: checked before the patterns, so a label can never hide a
# separator.
_HOSTNAME = re.compile(r"[a-z0-9][a-z0-9.-]*[a-z0-9](:[0-9]{1,5})?\Z")

# Local development is served over plain HTTP; everything else must be HTTPS.
_LOCAL = ("localhost", "127.0.0.1")


def _matches(host, pattern):
    """Label by label, so `*` cannot swallow a dot.

    `c1-review-*.cleverapps.io` must not accept `c1-review-a.evil.cleverapps.io`:
    a plain `fnmatch` would, since its `*` matches separators too.
    """
    host_labels = host.split(".")
    pattern_labels = pattern.split(".")
    if len(host_labels) != len(pattern_labels):
        return False
    return all(fnmatchcase(label, expected) for label, expected in zip(host_labels, pattern_labels))


def origin(request):
    """The platform origin this page's links and searches point at.

    No request means no host to honour — a preview, or a template rendered
    outside a view — so the default answers rather than raising: a link to the
    wrong environment beats a 500 on the public page.
    """
    host = request.GET.get("host", "").strip().lower() if request else ""
    if not host or not _HOSTNAME.fullmatch(host):
        return settings.PLATFORM_DEFAULT_ORIGIN
    if any(_matches(host, pattern) for pattern in settings.PLATFORM_ALLOWED_HOSTS):
        scheme = "http" if host.split(":")[0] in _LOCAL else "https"
        return f"{scheme}://{host}"
    return settings.PLATFORM_DEFAULT_ORIGIN


def url(request, path):
    """A platform-relative path, resolved against the host's origin."""
    return f"{origin(request)}{path}"
