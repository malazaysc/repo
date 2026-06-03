"""Celery ingestion pipeline.

ingest_note: parse the source → optionally summarize with AI → persist.
Designed to be idempotent-ish and to fail soft on the AI step.
"""
from __future__ import annotations

import logging
import mimetypes

import httpx
from celery import shared_task

from notes.models import Attachment, Note, NoteStatus, SourceType, Tag

from .ai import describe_image, summarize
from .images import download_attachments
from .parsers import ParserError, get_parser

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def ingest_note(self, note_id: int) -> str:
    try:
        note = Note.objects.get(pk=note_id)
    except Note.DoesNotExist:
        logger.warning("ingest_note: note %s no longer exists", note_id)
        return "missing"

    note.mark_processing()

    try:
        if note.source_url:
            _parse_from_url(note)
        # else: manual text note already has cleaned_text/raw_content.

        _run_ai(note)

        note.status = NoteStatus.DONE
        note.error_message = ""
        note.save(update_fields=["status", "error_message", "updated_at"])
        note.update_search_vector()
        return "done"

    except ParserError as exc:
        # Expected, user-actionable failure — don't retry.
        logger.info("ingest_note: parser error for note %s: %s", note_id, exc)
        _safe_mark_failed(note, str(exc))
        return "failed"
    except _TRANSIENT_ERRORS as exc:
        # Network blips — worth retrying.
        logger.warning("ingest_note: transient error for note %s: %s", note_id, exc)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            _safe_mark_failed(note, f"Temporary error, gave up after retries: {exc}")
            return "failed"
    except Exception as exc:
        # Deterministic bug — fail fast, don't burn the retry budget (C3).
        logger.exception("ingest_note: unexpected error for note %s", note_id)
        _safe_mark_failed(note, f"Unexpected error: {exc}")
        return "failed"


# Only network-ish failures are retried; everything else fails fast.
_TRANSIENT_ERRORS = (httpx.TransportError, ConnectionError, TimeoutError)


def _safe_mark_failed(note: Note, message: str) -> None:
    try:
        note.mark_failed(message)
    except Exception:
        logger.exception("ingest_note: could not mark note %s failed", note.pk)


def _parse_from_url(note: Note) -> None:
    parser = get_parser(note.source_url)
    # Reflect the resolved source type immediately so even a failed parse shows
    # the right badge (e.g. "X/Twitter" rather than the default "Article / Link").
    if note.source_type != parser.source_type:
        note.source_type = parser.source_type
        note.save(update_fields=["source_type", "updated_at"])

    result = parser.parse(note.source_url)

    note.source_type = result.source_type
    note.title = note.title or result.title
    note.raw_content = result.raw
    note.cleaned_text = result.text
    if result.metadata:
        note.metadata = {**note.metadata, **result.metadata}
    note.save(
        update_fields=[
            "source_type", "title", "raw_content", "cleaned_text", "metadata", "updated_at"
        ]
    )

    for img in result.images:
        if img.url:
            Attachment.objects.get_or_create(
                note=note,
                remote_url=img.url,
                defaults={"kind": Attachment.Kind.IMAGE, "caption": img.caption[:500]},
            )

    # Pull the images into local storage (non-fatal if any fail).
    download_attachments(note)


def _run_ai(note: Note) -> None:
    if note.cleaned_text.strip():
        result = summarize(note.title, note.cleaned_text)
    elif note.source_type == SourceType.IMAGE:
        result = _describe_note_image(note)
    else:
        result = None

    if not result:
        return

    note.summary = result.summary
    note.highlights = result.highlights
    # For image notes the description doubles as the searchable body.
    if note.source_type == SourceType.IMAGE and not note.cleaned_text.strip():
        note.cleaned_text = result.summary
    if not note.title and result.summary:
        note.title = result.summary[:120]
    note.save(update_fields=["summary", "highlights", "cleaned_text", "title", "updated_at"])

    for tag_name in result.tags:
        tag, _ = Tag.objects.get_or_create(name=tag_name)
        note.tags.add(tag)


def _describe_note_image(note: Note) -> object | None:
    """Caption the note's first locally-stored image via Claude vision."""
    att = note.attachments.exclude(file="").first()
    if not att or not att.file:
        return None
    media_type, _ = mimetypes.guess_type(att.file.name)
    if not media_type:
        return None
    try:
        with att.file.open("rb") as fh:
            data = fh.read()
    except OSError:
        return None
    return describe_image(data, media_type)
