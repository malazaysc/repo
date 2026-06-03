import pytest

from notes.models import Note, NoteStatus, SourceType

pytestmark = pytest.mark.django_db


def test_failed_parse_still_sets_source_type(user, monkeypatch):
    """A note that fails parsing should still show the resolved source type."""
    from ingestion import tasks
    from ingestion.parsers.base import ParserError

    # X parser is disabled by default -> parse() raises, but the badge should
    # reflect X rather than the default ARTICLE.
    note = Note.objects.create(
        owner=user,
        source_url="https://x.com/jack/status/20",
        status=NoteStatus.PENDING,
    )

    tasks.ingest_note.delay(note.pk)

    note.refresh_from_db()
    assert note.status == NoteStatus.FAILED
    assert note.source_type == SourceType.X
    assert "X capture is disabled" in note.error_message
