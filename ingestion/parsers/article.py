"""Generic article/link parser: extracts main text + images from any web page.

Uses trafilatura for robust main-content extraction, falling back to a simple
BeautifulSoup text dump if trafilatura finds nothing.
"""
from __future__ import annotations

from urllib.parse import urljoin

import httpx

from notes.models import SourceType

from .base import BaseParser, ParsedContent, ParsedImage, ParserError

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


class ArticleParser(BaseParser):
    name = "article"
    source_type = SourceType.ARTICLE

    def can_handle(self, url: str) -> bool:
        return url.startswith("http://") or url.startswith("https://")

    def parse(self, url: str) -> ParsedContent:
        html = self._fetch(url)

        title, text, metadata = self._extract_main(url, html)
        images = self._extract_images(url, html)

        if not text:
            raise ParserError("Could not extract readable text from this page.")

        return ParsedContent(
            source_type=SourceType.ARTICLE,
            title=title,
            text=text,
            raw=html[:200_000],
            metadata=metadata,
            images=images,
        )

    def _fetch(self, url: str) -> str:
        try:
            resp = httpx.get(url, headers=_HEADERS, follow_redirects=True, timeout=20.0)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ParserError(f"Failed to fetch the page: {exc}") from exc
        return resp.text

    def _extract_main(self, url: str, html: str) -> tuple[str, str, dict]:
        metadata: dict = {}
        title = ""
        text = ""
        try:
            import trafilatura

            extracted = trafilatura.extract(
                html, include_comments=False, include_images=False, url=url
            )
            if extracted:
                text = extracted.strip()
            meta = trafilatura.extract_metadata(html, default_url=url)
            if meta:
                title = meta.title or ""
                metadata = {
                    "author": meta.author,
                    "date": meta.date,
                    "sitename": meta.sitename,
                    "description": meta.description,
                }
        except Exception:
            pass

        if not text or not title:
            t2, txt2 = self._soup_fallback(html)
            title = title or t2
            text = text or txt2

        return title, text, {k: v for k, v in metadata.items() if v}

    def _soup_fallback(self, html: str) -> tuple[str, str]:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = "\n".join(
            line.strip() for line in soup.get_text("\n").splitlines() if line.strip()
        )
        return title, text

    def _extract_images(self, url: str, html: str, limit: int = 8) -> list[ParsedImage]:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        images: list[ParsedImage] = []

        # Prefer the OpenGraph image first.
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            images.append(ParsedImage(url=urljoin(url, og["content"]), caption="og:image"))

        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if not src:
                continue
            images.append(ParsedImage(url=urljoin(url, src), caption=img.get("alt", "")))
            if len(images) >= limit:
                break
        return images
