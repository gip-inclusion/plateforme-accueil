"""An editor's file, turned into an image the page can serve.

This module knows nothing of sections or forms: it takes a file and the
constraints the field declares, and returns a storage key. An editor uploads
whatever they have — a four-megabyte photo straight off a phone — and the page
stays light: the quality of a public page must not rest on the discipline of
whoever feeds it.
"""

import hashlib
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from PIL import Image, ImageOps

from accueil.sections.base import UPLOAD_PREFIX


QUALITY = 82
MAX_BYTES = 15 * 1024 * 1024
# Bounds memory use against a decompression bomb: a tiny, highly compressible
# file that decodes into a huge bitmap. Checked on the declared dimensions,
# before any pixel is decoded — well above what a real photo needs once
# resized to a page's `max_width`, well below what would blow up memory.
MAX_PIXELS = 50_000_000


def store(uploaded, *, max_width, ratio=None):
    """Crop, shrink, convert to WebP, and return the stored file's key."""
    # `uploaded.size` comes from the upload's Content-Length, known before a
    # single byte of the body is read: this check happens first, and cheaply.
    if uploaded.size > MAX_BYTES:
        raise ValidationError(f"L'image ne doit pas dépasser {MAX_BYTES // (1024 * 1024)} Mo.")

    try:
        image = Image.open(uploaded)
    except Exception as erreur:
        raise ValidationError("Ce fichier n'est pas une image lisible.") from erreur

    # `Image.open` only reads the header: dimensions are known here without
    # decoding any pixel data, so a bomb is refused before it is inflated.
    if image.width * image.height > MAX_PIXELS:
        raise ValidationError("Cette image compte trop de pixels pour être traitée.")

    try:
        image.load()
    except Exception as erreur:
        raise ValidationError("Ce fichier n'est pas une image lisible.") from erreur

    # A photo's orientation lives in its metadata: without this it arrives
    # lying on its side.
    image = ImageOps.exif_transpose(image)

    # A pictogram is often a flat PNG or WebP with a transparent background:
    # flattening it onto an implicit black backdrop would be wrong. Only
    # collapse to plain RGB when there is nothing to lose.
    has_alpha = image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info)
    image = image.convert("RGBA") if has_alpha else image.convert("RGB")

    # `fit` crops to the centre and resizes in one pass. Only the first frame
    # of an animated source (GIF, animated WebP) is used: illustrations on
    # this page are static content, never animated chrome.
    image = ImageOps.fit(image, _target(image, max_width, ratio), method=Image.LANCZOS)

    buffer = BytesIO()
    image.save(buffer, format="WEBP", quality=QUALITY)
    data = buffer.getvalue()

    # Naming by content gives three things at once: no duplicates, an immortal
    # cache, and no collision between editors.
    key = f"{UPLOAD_PREFIX}{hashlib.sha256(data).hexdigest()[:16]}.webp"
    storage = storages["default"]
    if not storage.exists(key):
        storage.save(key, ContentFile(data))
    return key


def _target(image, max_width, ratio):
    """Output dimensions: never wider than the source, nor than the field asks,
    and in the declared shape if there is one."""
    width = min(image.width, max_width)
    if ratio is None:
        return width, round(image.height * width / image.width)

    height = round(width * ratio[1] / ratio[0])
    if height > image.height:
        # Source too short for that shape: the height is what governs.
        height = image.height
        width = round(height * ratio[0] / ratio[1])
    return width, height
