"""An editor's file, turned into an image the page can serve.

This module knows nothing of sections or forms: it takes a file and the
constraints the field declares, and returns a storage key. An editor uploads
whatever they have — a four-megabyte photo straight off a phone — and the page
stays light: the quality of a public page must not rest on the discipline of
whoever feeds it.
"""

import hashlib
import logging
from contextlib import ExitStack
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from PIL import Image, ImageOps


logger = logging.getLogger(__name__)

UPLOAD_PREFIX = "uploads/"  # tells an uploaded file's storage key apart from a static path

# 82 is a measured choice, not a default left alone: on the illustrations
# actually shipped (shaded artwork, not flat vector art), lossless WebP costs
# 3-4x the bytes for an RMS improvement of ~4/255 — not worth it. `WEBP`'s
# `alpha_quality` defaults to 100, which we rely on so a pictogram's edge
# against its transparent background doesn't fringe.
QUALITY = 82

MAX_BYTES = 15 * 1024 * 1024

# A memory bound, not a fidelity one: the widest `max_width` declared anywhere
# on the page is 940px, so any source above a few megapixels is already far
# more detail than the output can use. 24 megapixels comfortably covers a
# modern phone photo (commonly 12-24MP) while keeping the decoded RGBA buffer
# under ~100MB on a container sized to serve a static page. Checked on the
# declared dimensions, before any pixel is decoded, so an oversized source is
# refused before it is inflated.
MAX_PIXELS = 24_000_000

# What Pillow actually raises for a file that isn't a readable image:
# `UnidentifiedImageError` (a format it doesn't recognise) and `OSError` (a
# truncated or corrupt body) from `Image.open`/`.load`, and `ValueError` for a
# handful of malformed-header cases in specific decoders. Anything else
# (`MemoryError`, a `TypeError` in our own code, a storage hiccup) is not "the
# editor's file is unreadable" and must not be reported as such.
UNREADABLE_IMAGE_ERRORS = (Image.UnidentifiedImageError, OSError, ValueError)


def store(uploaded, *, max_width, ratio=None):
    """Crop, shrink, convert to WebP, and return the stored file's key."""
    # `uploaded.size` is the size Django's upload handling already received in
    # full (buffered in memory or to a temp file before any view code runs) —
    # not a header read ahead of the body. So this check is cheap and correct,
    # but it does not bound what hits the network; it only stops a large file
    # from reaching Pillow.
    if uploaded.size > MAX_BYTES:
        raise ValidationError(f"L'image ne doit pas dépasser {MAX_BYTES // (1024 * 1024)} Mo.")

    with ExitStack() as stack:
        try:
            image = Image.open(uploaded)
        except UNREADABLE_IMAGE_ERRORS as erreur:
            raise ValidationError("Ce fichier n'est pas une image lisible.") from erreur
        except Exception:
            logger.exception("Unexpected error while opening an uploaded file")
            raise ValidationError("Ce fichier n'est pas une image lisible.") from None
        stack.callback(image.close)

        # `Image.open` only reads the header: dimensions are known here
        # without decoding any pixel data, so a bomb is refused before it is
        # inflated.
        if image.width * image.height > MAX_PIXELS:
            raise ValidationError("Cette image compte trop de pixels pour être traitée.")

        try:
            image.load()
        except UNREADABLE_IMAGE_ERRORS as erreur:
            raise ValidationError("Ce fichier n'est pas une image lisible.") from erreur
        except Exception:
            logger.exception("Unexpected error while decoding an uploaded image")
            raise ValidationError("Ce fichier n'est pas une image lisible.") from None

        # A photo's orientation lives in its metadata: without this it arrives
        # lying on its side. `in_place` avoids an unconditional extra copy of
        # the full-size bitmap that `exif_transpose` otherwise makes even when
        # there is no Orientation tag to apply — the common case for PNG/WebP
        # sources, which have no EXIF at all.
        ImageOps.exif_transpose(image, in_place=True)

        # A pictogram is often a flat PNG or WebP with a transparent
        # background: flattening it onto an implicit black backdrop would be
        # wrong. Only collapse to plain RGB when there is nothing to lose.
        has_alpha = image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info)
        converted = image.convert("RGBA") if has_alpha else image.convert("RGB")
        stack.callback(converted.close)

        # `fit` crops to the centre and resizes in one pass. Only the first
        # frame of an animated source (GIF, animated WebP) is used:
        # illustrations on this page are static content, never animated
        # chrome.
        fitted = ImageOps.fit(converted, _target(converted, max_width, ratio), method=Image.LANCZOS)
        stack.callback(fitted.close)

        buffer = BytesIO()
        fitted.save(buffer, format="WEBP", quality=QUALITY)
        data = buffer.getvalue()

    # Naming by content gives three things at once: no duplicates, an immortal
    # cache, and no collision between editors. It is also what makes the
    # check-then-act race below harmless: two concurrent uploads of identical
    # bytes both compute the same key, so even if both see `exists()` return
    # `False`, whichever write "wins" (or, on local disk, the suffixed orphan
    # the loser produces) holds the exact same content either way.
    key = f"{UPLOAD_PREFIX}{hashlib.sha256(data).hexdigest()[:16]}.webp"
    storage = storages["default"]
    if not storage.exists(key):
        # The return value (the name actually stored under) is discarded on
        # purpose: `key` is already the content-hashed name we want callers to
        # use, and is what makes a repeated upload resolve to the same file.
        storage.save(key, ContentFile(data))
    return key


def _target(image, max_width, ratio):
    """Output dimensions: never wider than the source, nor than the field asks,
    and in the declared shape if there is one.

    Every `round()` here is clamped to at least 1px: an extreme source (a
    1px-tall banner, a near-square crop against a very wide or very tall
    ratio) can round a dimension down to 0, which `ImageOps.fit` cannot
    handle — banker's rounding makes `round(0.5) == 0`, so this is not just a
    theoretical edge.
    """
    width = min(image.width, max_width)
    if ratio is None:
        return width, max(1, round(image.height * width / image.width))

    height = max(1, round(width * ratio[1] / ratio[0]))
    if height > image.height:
        # Source too short for that shape: the height is what governs.
        height = image.height
        width = max(1, round(height * ratio[0] / ratio[1]))
    return width, height
