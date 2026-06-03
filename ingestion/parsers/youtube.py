"""YouTube parser: pulls the transcript (if available) + video metadata."""
from __future__ import annotations

import re
from urllib.parse import urlparse

from notes.models import SourceType

from .base import BaseParser, ParsedContent, ParsedImage, ParserError

_YT_HOSTS = frozenset({"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"})
_VIDEO_ID_RE = re.compile(
    r"(?:v=|/embed/|/shorts/|youtu\.be/)([0-9A-Za-z_-]{11})"
)


def extract_video_id(url: str) -> str | None:
    match = _VIDEO_ID_RE.search(url)
    return match.group(1) if match else None


class YouTubeParser(BaseParser):
    name = "youtube"
    source_type = SourceType.YOUTUBE

    def can_handle(self, url: str) -> bool:
        host = (urlparse(url).hostname or "").lower()
        return host in _YT_HOSTS and extract_video_id(url) is not None

    def parse(self, url: str) -> ParsedContent:
        video_id = extract_video_id(url)
        if not video_id:
            raise ParserError("Could not extract a YouTube video ID from the URL.")

        metadata = self._fetch_metadata(url)
        transcript, language = self._fetch_transcript(video_id)

        if not transcript:
            raise ParserError(
                "No transcript available for this video. You can paste the text manually."
            )
        if language:
            metadata["transcript_language"] = language

        title = metadata.get("title") or f"YouTube video {video_id}"
        images = []
        if thumb := metadata.get("thumbnail"):
            images.append(ParsedImage(url=thumb, caption="thumbnail"))

        return ParsedContent(
            source_type=SourceType.YOUTUBE,
            title=title,
            text=transcript,
            raw=transcript,
            metadata=metadata,
            images=images,
        )

    def _fetch_transcript(self, video_id: str) -> tuple[str, str]:
        """Return (text, language_code).

        Tries the configured preferred languages first, then falls back to any
        transcript that exists — in its own language — so non-English videos
        (e.g. Spanish-only auto-captions) still ingest without translation.
        """
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
        except ImportError as exc:  # pragma: no cover
            raise ParserError("youtube-transcript-api is not installed.") from exc

        from django.conf import settings

        languages = list(getattr(settings, "YOUTUBE_TRANSCRIPT_LANGUAGES", ["en", "es"]))
        api = YouTubeTranscriptApi()

        # 1) Preferred languages in priority order.
        try:
            fetched = api.fetch(video_id, languages=languages)
            return self._join(fetched), getattr(fetched, "language_code", "")
        except Exception:
            pass

        # 2) Fallback: accept any available transcript, keeping its language.
        try:
            transcript_list = api.list(video_id)
        except Exception as exc:  # video has no captions at all / unavailable
            raise ParserError(f"Transcript unavailable: {exc}") from exc

        transcript = next(iter(transcript_list), None)
        if transcript is None:
            raise ParserError("No transcript available for this video.")

        try:
            fetched = transcript.fetch()
        except Exception as exc:
            raise ParserError(f"Transcript unavailable: {exc}") from exc

        return self._join(fetched), getattr(transcript, "language_code", "")

    @staticmethod
    def _join(fetched) -> str:
        return "\n".join(snippet.text for snippet in fetched).strip()

    def _fetch_metadata(self, url: str) -> dict:
        try:
            import yt_dlp
        except ImportError:  # pragma: no cover
            return {}

        opts = {"quiet": True, "skip_download": True, "no_warnings": True}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception:
            return {}

        return {
            "title": info.get("title"),
            "channel": info.get("uploader") or info.get("channel"),
            "duration_seconds": info.get("duration"),
            "upload_date": info.get("upload_date"),
            "view_count": info.get("view_count"),
            "thumbnail": info.get("thumbnail"),
            "webpage_url": info.get("webpage_url"),
        }
