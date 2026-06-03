"""Parser strategy interface.

Adding a new source = implement a ``BaseParser`` subclass and register it.
Each parser declares whether it ``can_handle`` a URL and how to ``parse`` it
into a normalized :class:`ParsedContent`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from notes.models import SourceType


@dataclass
class ParsedImage:
    url: str = ""
    caption: str = ""


@dataclass
class ParsedContent:
    """Normalized result every parser returns."""

    source_type: str = SourceType.ARTICLE
    title: str = ""
    text: str = ""
    raw: str = ""
    metadata: dict = field(default_factory=dict)
    images: list[ParsedImage] = field(default_factory=list)


class ParserError(Exception):
    """Raised when a parser cannot extract usable content."""


class BaseParser:
    #: Human-friendly name for logging.
    name: str = "base"
    #: The SourceType this parser produces.
    source_type: str = SourceType.ARTICLE

    def can_handle(self, url: str) -> bool:  # pragma: no cover - interface
        raise NotImplementedError

    def parse(self, url: str) -> ParsedContent:  # pragma: no cover - interface
        raise NotImplementedError
