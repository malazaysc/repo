import pytest
from django.core.files.base import ContentFile
from django.test import override_settings

from ingestion.ai import AISummary
from ingestion.ai import client as ai_client
from ingestion.ai.client import _parse_response, summarize
from notes.models import Note, NoteStatus, SourceType

# --- Fake Anthropic client -------------------------------------------------

class _Block:
    type = "text"

    def __init__(self, text):
        self.text = text


class _Msg:
    def __init__(self, text):
        self.content = [_Block(text)]


class _FakeClient:
    def __init__(self, text):
        self._text = text

    @property
    def messages(self):
        return self

    def create(self, **kwargs):
        return _Msg(self._text)


# --- _parse_response -------------------------------------------------------

def test_parse_response_plain_json():
    res = _parse_response('{"summary":"S","highlights":["h1","h2"],"tags":["AI","ML"]}')
    assert res.summary == "S"
    assert res.highlights == ["h1", "h2"]
    assert res.tags == ["ai", "ml"]  # normalized to lowercase


def test_parse_response_fenced_json():
    raw = 'Here you go:\n```json\n{"summary":"x","tags":["a"]}\n```'
    res = _parse_response(raw)
    assert res.summary == "x"
    assert res.tags == ["a"]


def test_parse_response_refusal_returns_none():
    # A non-JSON model reply (e.g. a refusal) must NOT become the note body (C4).
    assert _parse_response("I can't help with that.") is None


def test_parse_response_empty_json_returns_none():
    assert _parse_response('{"summary":"","highlights":[],"tags":[]}') is None


# --- summarize gating ------------------------------------------------------

@override_settings(AI_SUMMARY_ENABLED=False)
def test_summarize_disabled_returns_none():
    assert summarize("t", "some text") is None


@override_settings(AI_SUMMARY_ENABLED=True, ANTHROPIC_API_KEY="")
def test_summarize_no_key_returns_none():
    assert summarize("t", "some text") is None


@override_settings(AI_SUMMARY_ENABLED=True, ANTHROPIC_API_KEY="sk-test")
def test_summarize_parses_mocked_response(monkeypatch):
    payload = '{"summary":"A summary","highlights":["k1"],"tags":["python"]}'
    monkeypatch.setattr(ai_client, "_client", lambda: _FakeClient(payload))
    res = summarize("Title", "long content here")
    assert isinstance(res, AISummary)
    assert res.summary == "A summary"
    assert res.tags == ["python"]


# --- full ingest applies tags (eager celery) -------------------------------

@pytest.mark.django_db
def test_ingest_text_note_applies_ai_tags(user, monkeypatch):
    from ingestion import tasks

    monkeypatch.setattr(
        tasks,
        "summarize",
        lambda title, text: AISummary(summary="Sum", highlights=["a"], tags=["python", "django"]),
    )
    note = Note.objects.create(
        owner=user,
        source_type=SourceType.TEXT,
        cleaned_text="hello world",
        status=NoteStatus.PENDING,
    )

    tasks.ingest_note.delay(note.pk)

    note.refresh_from_db()
    assert note.status == NoteStatus.DONE
    assert note.summary == "Sum"
    assert set(note.tags.values_list("name", flat=True)) == {"python", "django"}


@pytest.mark.django_db
def test_ingest_image_note_uses_vision(user, monkeypatch):
    from ingestion import tasks

    monkeypatch.setattr(
        tasks,
        "describe_image",
        lambda data, media_type: AISummary(summary="A cat sitting", tags=["cat"]),
    )
    note = Note.objects.create(
        owner=user, source_type=SourceType.IMAGE, status=NoteStatus.PENDING
    )
    att = note.attachments.create(kind="image")
    att.file.save("cat.png", ContentFile(b"\x89PNGfake"), save=True)

    tasks.ingest_note.delay(note.pk)

    note.refresh_from_db()
    assert note.status == NoteStatus.DONE
    assert note.cleaned_text == "A cat sitting"  # description doubles as body
    assert "cat" in set(note.tags.values_list("name", flat=True))
