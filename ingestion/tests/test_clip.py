import json

import pytest
from django.test import override_settings
from django.urls import reverse

from notes.models import Note, NoteStatus, SourceType

pytestmark = pytest.mark.django_db

TOKEN = "test-clip-token"  # matches config/settings/test.py


@pytest.fixture
def superuser(django_user_model):
    return django_user_model.objects.create_superuser("admin", "a@example.com", "pw")


def _post(client, body, token=TOKEN):
    headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
    return client.post(
        reverse("clip"), data=json.dumps(body), content_type="application/json", **headers
    )


def test_clip_rejects_missing_token(client, superuser):
    resp = _post(client, {"text": "hi"}, token=None)
    assert resp.status_code == 403
    assert Note.objects.count() == 0


def test_clip_rejects_bad_token(client, superuser):
    resp = _post(client, {"text": "hi"}, token="wrong")
    assert resp.status_code == 403


@override_settings(CLIP_TOKEN="")
def test_clip_disabled_without_token_setting(client, superuser):
    resp = _post(client, {"text": "hi"})
    assert resp.status_code == 503


def test_clip_creates_note_and_runs_pipeline(client, superuser, monkeypatch):
    # Avoid a real image download during the eager pipeline.
    from ingestion import tasks

    monkeypatch.setattr(tasks, "download_attachments", lambda note: 0)
    resp = _post(
        client,
        {
            "url": "https://x.com/jack/status/20",
            "title": "A tweet",
            "text": "hello from the clipper",
            "images": ["https://pbs.twimg.com/media/abc.jpg"],
        },
    )
    assert resp.status_code == 201
    payload = resp.json()
    note = Note.objects.get(pk=payload["id"])
    # Eager Celery ran the pipeline inline.
    assert note.status == NoteStatus.DONE
    assert note.source_type == SourceType.X  # detected from the URL
    assert note.cleaned_text == "hello from the clipper"
    assert note.title == "A tweet"
    assert note.owner == superuser
    assert note.attachments.count() == 1


def test_clip_clipped_note_is_not_refetched(client, superuser, monkeypatch):
    # If content is provided, the pipeline must NOT call the URL parser/fetch.
    from ingestion import tasks

    def boom(note):
        raise AssertionError("must not fetch a clipped note")

    monkeypatch.setattr(tasks, "_parse_from_url", boom)
    resp = _post(
        client,
        {"url": "https://example.com/article", "title": "T", "text": "provided body"},
    )
    assert resp.status_code == 201
    assert Note.objects.get(pk=resp.json()["id"]).status == NoteStatus.DONE


def test_clip_requires_content(client, superuser):
    resp = _post(client, {"title": "empty"})
    assert resp.status_code == 400
