"""X (Twitter) parser — routing stub.

X aggressively blocks server-side scraping, so X content is added via the
"Clip to Notes" browser extension (it reads the page from your logged-in
session and POSTs it to `/api/clip/`). This parser only exists so X URLs are
recognized (for `source_type`) and so pasting an X URL into the "Add source"
bar returns a helpful message pointing at the extension.
"""
from __future__ import annotations

from urllib.parse import urlparse

from notes.models import SourceType

from .base import BaseParser, ParsedContent, ParserError

X_HOSTS = frozenset(
    {"twitter.com", "x.com", "www.twitter.com", "www.x.com", "mobile.twitter.com"}
)


class XParser(BaseParser):
    name = "x"
    source_type = SourceType.X

    def can_handle(self, url: str) -> bool:
        host = (urlparse(url).hostname or "").lower()
        return host in X_HOSTS

    def parse(self, url: str) -> ParsedContent:
        raise ParserError(
            "X pages can't be fetched server-side — add them with the "
            "‘Clip to Notes’ browser extension instead."
        )
