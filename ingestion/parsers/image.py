"""Bare image URL parser.

Handles links that point directly at an image file (``.jpg``, ``.png``, …).
The image itself is recorded as an attachment; the download step later fetches
the bytes into local storage. Optional AI captioning/OCR can enrich the text
later (see the AI layer).
"""
from __future__ import annotations

import os
from urllib.parse import urlparse

from notes.models import SourceType

from .base import BaseParser, ParsedContent, ParsedImage

IMAGE_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".bmp",
    ".svg",
    ".avif",
    ".tiff",
)


class ImageParser(BaseParser):
    name = "image"
    source_type = SourceType.IMAGE

    def can_handle(self, url: str) -> bool:
        if not (url.startswith("http://") or url.startswith("https://")):
            return False
        path = urlparse(url).path.lower()
        return path.endswith(IMAGE_EXTENSIONS)

    def parse(self, url: str) -> ParsedContent:
        filename = os.path.basename(urlparse(url).path) or "image"
        return ParsedContent(
            source_type=SourceType.IMAGE,
            title=filename,
            text="",
            raw=url,
            metadata={"image_url": url},
            images=[ParsedImage(url=url, caption=filename)],
        )
