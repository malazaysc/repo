"""Pluggable AI summarization.

Currently backed by the Claude API. Designed so the provider can be swapped
(local Ollama, etc.) behind ``summarize()`` without touching callers.

Returns suggested summary, highlights, and tags. Fails soft: if AI is disabled
or errors, callers get ``None`` and the note ingests without a summary.
"""
from __future__ import annotations

import functools
import json
import logging
from dataclasses import dataclass, field

from django.conf import settings

logger = logging.getLogger(__name__)

# Cap input tokens roughly by trimming very long text before sending.
_MAX_CHARS = 48_000

_SYSTEM_PROMPT = (
    "You are a note-taking assistant. Given the text content of a web source "
    "(article, video transcript, or post), produce a concise, faithful summary. "
    "Do not invent facts. Respond ONLY with a JSON object matching the schema."
)

_SCHEMA_HINT = """Return JSON exactly like:
{
  "summary": "2-4 sentence summary",
  "highlights": ["key point 1", "key point 2", "..."],
  "tags": ["lowercase-topic", "..."]
}"""

_IMAGE_SYSTEM_PROMPT = (
    "You are a note-taking assistant. Describe the given image faithfully and "
    "transcribe any visible text (OCR). Do not invent details. Respond ONLY with "
    "a JSON object matching the schema."
)


def _ai_ready() -> bool:
    if not settings.AI_SUMMARY_ENABLED:
        return False
    if not settings.ANTHROPIC_API_KEY:
        logger.warning("AI_SUMMARY_ENABLED but ANTHROPIC_API_KEY is empty; skipping.")
        return False
    return True


@functools.lru_cache(maxsize=1)
def _build_client(api_key: str):
    import anthropic

    return anthropic.Anthropic(api_key=api_key)


def _client():
    # Reuse one client (and its connection pool) across ingests (Q5).
    return _build_client(settings.ANTHROPIC_API_KEY)


@dataclass
class AISummary:
    summary: str = ""
    highlights: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


def summarize(title: str, text: str) -> AISummary | None:
    if not _ai_ready() or not text.strip():
        return None

    try:
        client = _client()
    except ImportError:  # pragma: no cover
        logger.warning("anthropic SDK not installed; skipping summary.")
        return None

    content = text[:_MAX_CHARS]
    user_text = (
        f"Source title: {title or '(untitled)'}\n\n"
        f"{_SCHEMA_HINT}\n\n--- CONTENT ---\n{content}"
    )

    try:
        msg = client.messages.create(
            model=settings.AI_SUMMARY_MODEL,
            max_tokens=1024,
            system=[
                {
                    "type": "text",
                    "text": _SYSTEM_PROMPT,
                    # Cache the static system prompt across ingests.
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_text}],
        )
    except Exception as exc:
        logger.warning("AI summarize failed: %s", exc)
        return None

    raw = "".join(block.text for block in msg.content if block.type == "text").strip()
    return _parse_response(raw)


def describe_image(image_bytes: bytes, media_type: str) -> AISummary | None:
    """Caption + OCR an image via Claude vision. Fails soft to None."""
    if not _ai_ready() or not image_bytes:
        return None
    if media_type not in {"image/jpeg", "image/png", "image/gif", "image/webp"}:
        return None

    try:
        client = _client()
    except ImportError:  # pragma: no cover
        return None

    import base64

    b64 = base64.standard_b64encode(image_bytes).decode()
    try:
        msg = client.messages.create(
            model=settings.AI_SUMMARY_MODEL,
            max_tokens=1024,
            system=[
                {
                    "type": "text",
                    "text": _IMAGE_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": _SCHEMA_HINT},
                    ],
                }
            ],
        )
    except Exception as exc:
        logger.warning("AI image description failed: %s", exc)
        return None

    raw = "".join(block.text for block in msg.content if block.type == "text").strip()
    return _parse_response(raw)


def _parse_response(raw: str) -> AISummary | None:
    # Tolerate models that wrap JSON in prose or code fences. If there's no JSON
    # object at all (e.g. a model refusal), treat it as "no summary" rather than
    # persisting raw prose as the note body (C4).
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        logger.info("AI response had no JSON object; skipping summary.")
        return None
    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        logger.info("AI response JSON was malformed; skipping summary.")
        return None

    result = AISummary(
        summary=str(data.get("summary", "")).strip(),
        highlights=[str(h) for h in data.get("highlights", []) if h][:12],
        tags=[str(t).lower().strip() for t in data.get("tags", []) if t][:8],
    )
    # Nothing usable parsed out — don't overwrite content with an empty summary.
    if not result.summary and not result.highlights and not result.tags:
        return None
    return result
