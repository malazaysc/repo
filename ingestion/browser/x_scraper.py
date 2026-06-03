"""Authenticated-browser scraping for X / Twitter via Playwright.

X has no free API and blocks anonymous scraping, so we drive a headless
Chromium loaded with a previously-captured *authenticated* session
(``storage_state``). Capture one with::

    python manage.py capture_x_session

The Playwright import is lazy so the rest of the app runs without it installed.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# Selectors are heuristic — X changes its DOM often; keep them in one place.
_TWEET_TEXT = '[data-testid="tweetText"]'
_USER_NAME = '[data-testid="User-Name"]'
_TWEET_PHOTO = '[data-testid="tweetPhoto"] img'
_WAIT_FOR = f"{_TWEET_TEXT}, article"


class XScrapeError(Exception):
    """Raised when the browser scrape cannot produce usable content."""


def scrape_x(
    url: str,
    *,
    storage_state_path: str | None,
    headless: bool = True,
    timeout_ms: int = 30_000,
) -> dict:
    """Return ``{title, text, images, metadata}`` for an X post/article.

    Raises :class:`XScrapeError` (or ImportError) on failure so the caller can
    surface a friendly message.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - exercised via parser test
        raise XScrapeError(
            "Playwright isn't installed. Add the 'browser' dependency group and "
            "run `playwright install chromium`."
        ) from exc

    use_state = bool(storage_state_path and os.path.exists(storage_state_path))
    if not use_state:
        logger.warning("X scrape running without a saved session — likely to be blocked.")

    result = {"title": "", "text": "", "images": [], "metadata": {}}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            storage_state=storage_state_path if use_state else None,
            viewport={"width": 1280, "height": 1600},
        )
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            try:
                page.wait_for_selector(_WAIT_FOR, timeout=timeout_ms)
            except Exception:
                pass  # fall through to whatever text we can grab

            _extract(page, result)
        finally:
            context.close()
            browser.close()

    if not result["text"].strip():
        raise XScrapeError(
            "Could not extract post content. The session may be expired or the "
            "post is unavailable. Re-capture with `manage.py capture_x_session`."
        )

    result["title"] = result["text"].split("\n")[0][:120] or "X post"
    return result


def _extract(page, result: dict) -> None:
    # Primary tweet text (a thread yields several tweetText nodes; join them).
    try:
        texts = page.locator(_TWEET_TEXT).all_inner_texts()
    except Exception:
        texts = []
    if texts:
        result["text"] = "\n\n".join(t.strip() for t in texts if t.strip())
    else:
        try:
            result["text"] = page.locator("article").first.inner_text().strip()
        except Exception:
            result["text"] = ""

    try:
        author = page.locator(_USER_NAME).first.inner_text()
        result["metadata"]["author"] = author.split("\n")[0].strip()
    except Exception:
        pass

    try:
        for img in page.locator(_TWEET_PHOTO).all():
            src = img.get_attribute("src")
            if src:
                result["images"].append(src)
    except Exception:
        pass
