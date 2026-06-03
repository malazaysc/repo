import pytest
from django.urls import reverse

from notes.forms import AddSourceForm
from notes.models import Note, NoteStatus, SourceType

pytestmark = pytest.mark.django_db


def test_form_rejects_non_http_scheme():
    form = AddSourceForm(data={"source_url": "ftp://example.com/file"})
    assert not form.is_valid()
    assert "source_url" in form.errors


def test_form_accepts_https():
    form = AddSourceForm(data={"source_url": "https://example.com/post"})
    assert form.is_valid(), form.errors


def test_form_requires_url_or_text():
    form = AddSourceForm(data={})
    assert not form.is_valid()


def test_note_edit_invalid_shows_error_not_silent(auth_client, user):
    note = Note.objects.create(
        owner=user, title="orig", cleaned_text="body", status=NoteStatus.DONE,
        source_type=SourceType.ARTICLE,
    )
    # title max_length is 500 — overflow makes the form invalid.
    resp = auth_client.post(
        reverse("notes:edit", args=[note.pk]),
        {"title": "x" * 600, "cleaned_text": "body", "summary": ""},
    )
    assert resp.status_code == 422
    assert b"Couldn" in resp.content  # error surfaced, not a silent redirect
    note.refresh_from_db()
    assert note.title == "orig"  # unchanged


def test_note_edit_valid_saves_and_redirects(auth_client, user):
    note = Note.objects.create(
        owner=user, title="orig", cleaned_text="body", status=NoteStatus.DONE,
    )
    resp = auth_client.post(
        reverse("notes:edit", args=[note.pk]),
        {"title": "updated", "cleaned_text": "new body", "summary": "s"},
    )
    assert resp.status_code == 302
    note.refresh_from_db()
    assert note.title == "updated"
