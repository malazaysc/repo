"""Download remote attachment images into local storage.

Attachments are created with a ``remote_url`` during parsing; this fetches the
bytes into ``Attachment.file`` so notes don't depend on (or leak referers to)
the origin. Failures are non-fatal — the ``remote_url`` stays as a fallback.
"""
from __future__ import annotations

import logging
import mimetypes
import os
from urllib.parse import urlparse

from django.core.files.base import ContentFile

from notes.models import Note

from .net import safe_get

logger = logging.getLogger(__name__)

# Skip absurdly large downloads (bytes).
MAX_IMAGE_BYTES = 15 * 1024 * 1024

# Disallowed image content types (active content / XSS risk). See S7.
_BLOCKED_CONTENT_TYPES = {"image/svg+xml"}


def _filename_for(url: str, content_type: str | None) -> str:
    name = os.path.basename(urlparse(url).path) or "image"
    root, ext = os.path.splitext(name)
    if not ext and content_type:
        guessed = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if guessed:
            name = f"{root or 'image'}{guessed}"
    return name[:120]


def download_attachments(note: Note, *, limit: int = 12) -> int:
    """Fetch any attachments that have a remote_url but no local file.

    Returns the number of images successfully stored locally.
    """
    stored = 0
    pending = note.attachments.filter(file="").exclude(remote_url="")[:limit]
    for att in pending:
        try:
            content, resp = safe_get(att.remote_url, max_bytes=MAX_IMAGE_BYTES)
        except Exception as exc:  # SSRF/size guard (UnsafeURLError) + transport errors
            logger.info("attachment download skipped (%s): %s", att.remote_url, exc)
            continue

        if not content:
            continue
        content_type = resp.headers.get("content-type", "").split(";")[0].strip().lower()
        if content_type and not content_type.startswith("image/"):
            # Not actually an image — leave the remote_url reference as-is.
            continue
        if content_type in _BLOCKED_CONTENT_TYPES:
            logger.info("attachment blocked (type %s): %s", content_type, att.remote_url)
            continue

        filename = _filename_for(att.remote_url, content_type)
        att.file.save(filename, ContentFile(content), save=True)
        stored += 1

    return stored
