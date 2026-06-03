"""Generic article/link parser: extracts main text + images from any web page.

Uses trafilatura for robust main-content extraction, falling back to a simple
BeautifulSoup text dump if trafilatura finds nothing.
"""
from __future__ import annotations

from urllib.parse import urljoin

from notes.models import SourceType

from ..net import UnsafeURLError, safe_get_text
from .base import BaseParser, ParsedContent, ParsedImage, ParserError

# Cap article HTML to bound memory (S2).
MAX_HTML_BYTES = 10 * 1024 * 1024


class ArticleParser(BaseParser):
    name = "article"
    source_type = SourceType.ARTICLE

    def can_handle(self, url: str) -> bool:
        return url.startswith("http://") or url.startswith("https://")

    def parse(self, url: str) -> ParsedContent:
        html = self._fetch(url)

        title, text, metadata = self._extract_main(url, html)
        # Image extraction is best-effort — never let it fail an otherwise-good parse.
        try:
            images = self._extract_images(url, html)
        except Exception:
            images = []

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
            return safe_get_text(url, max_bytes=MAX_HTML_BYTES)
        except UnsafeURLError as exc:
            raise ParserError(f"Refusing to fetch this URL: {exc}") from exc
        except Exception as exc:  # httpx transport/status errors
            raise ParserError(f"Failed to fetch the page: {exc}") from exc

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
        og_content = og.get("content") if og else None
        if isinstance(og_content, str) and og_content:
            images.append(ParsedImage(url=urljoin(url, og_content), caption="og:image"))

        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if not isinstance(src, str) or not src:
                continue
            alt = img.get("alt", "")
            images.append(ParsedImage(url=urljoin(url, src), caption=alt if isinstance(alt, str) else ""))
            if len(images) >= limit:
                break
        return images
