"""X (Twitter) parser — authenticated-browser capture via Playwright.

X has no free official API and blocks anonymous scraping, so this drives a
headless Chromium loaded with a saved authenticated session. Enable it with
``X_PARSER_ENABLED=1`` after capturing a session:

    python manage.py capture_x_session

Until then (or if the session is missing) it raises a friendly error telling
the user to capture a session or paste the content manually.
"""
from __future__ import annotations

import os

from django.conf import settings

from notes.models import SourceType

from ..browser import x_scraper
from .base import BaseParser, ParsedContent, ParsedImage, ParserError

_X_HOSTS = ("twitter.com", "x.com", "www.twitter.com", "www.x.com", "mobile.twitter.com")


class XParser(BaseParser):
    name = "x"
    source_type = SourceType.X

    def can_handle(self, url: str) -> bool:
        return any(f"//{host}/" in url or url.startswith(f"https://{host}") for host in _X_HOSTS)

    def parse(self, url: str) -> ParsedContent:
        if not getattr(settings, "X_PARSER_ENABLED", False):
            raise ParserError(
                "X capture is disabled. Set X_PARSER_ENABLED=1 and capture a session "
                "with `manage.py capture_x_session`, or use 'paste text instead'."
            )

        state_path = getattr(settings, "X_STORAGE_STATE_PATH", "")
        if not state_path or not os.path.exists(state_path):
            raise ParserError(
                "No saved X session found. Run `manage.py capture_x_session` to log in "
                "once, or use 'paste text instead'."
            )

        try:
            data = x_scraper.scrape_x(
                url,
                storage_state_path=state_path,
                headless=getattr(settings, "X_HEADLESS", True),
            )
        except x_scraper.XScrapeError as exc:
            raise ParserError(str(exc)) from exc

        return ParsedContent(
            source_type=SourceType.X,
            title=data.get("title", ""),
            text=data.get("text", ""),
            raw=data.get("text", ""),
            metadata=data.get("metadata", {}),
            images=[ParsedImage(url=u, caption="") for u in data.get("images", [])],
        )
