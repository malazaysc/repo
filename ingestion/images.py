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

import httpx
from django.core.files.base import ContentFile

from notes.models import Note

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# Skip absurdly large downloads (bytes).
MAX_IMAGE_BYTES = 15 * 1024 * 1024


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
            resp = httpx.get(
                att.remote_url, headers=_HEADERS, follow_redirects=True, timeout=20.0
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.info("attachment download failed (%s): %s", att.remote_url, exc)
            continue

        content = resp.content
        if not content or len(content) > MAX_IMAGE_BYTES:
            continue
        content_type = resp.headers.get("content-type", "")
        if content_type and not content_type.startswith("image/"):
            # Not actually an image — leave the remote_url reference as-is.
            continue

        filename = _filename_for(att.remote_url, content_type)
        att.file.save(filename, ContentFile(content), save=True)
        stored += 1

    return stored
