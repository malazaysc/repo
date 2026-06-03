"""Parser registry — resolves a URL to the first parser that can handle it.

Order matters: more specific parsers (YouTube, X) are tried before the
generic article parser, which acts as the catch-all fallback.
"""
from __future__ import annotations

from .article import ArticleParser
from .base import BaseParser
from .image import ImageParser
from .x import XParser
from .youtube import YouTubeParser

# Registration order = resolution priority.
_PARSERS: list[BaseParser] = [
    YouTubeParser(),
    XParser(),
    ImageParser(),  # bare image URLs (.jpg/.png/...) before the generic fallback.
    ArticleParser(),  # fallback — handles any http(s) URL.
]


def get_parser(url: str) -> BaseParser:
    for parser in _PARSERS:
        if parser.can_handle(url):
            return parser
    # ArticleParser.can_handle accepts any http(s) URL, so we rarely reach here.
    raise ValueError(f"No parser can handle URL: {url}")


def all_parsers() -> list[BaseParser]:
    return list(_PARSERS)
