import httpx
import pytest

from ingestion import images
from ingestion.images import download_attachments
from ingestion.net import UnsafeURLError
from ingestion.parsers.image import ImageParser
from notes.models import Note, NoteStatus, SourceType


def test_image_parser_parses_bare_url():
    result = ImageParser().parse("https://example.com/dir/sunset.png")
    assert result.source_type == SourceType.IMAGE
    assert result.title == "sunset.png"
    assert len(result.images) == 1
    assert result.images[0].url == "https://example.com/dir/sunset.png"


def test_image_parser_rejects_non_image():
    assert ImageParser().can_handle("https://example.com/article") is False


def test_image_parser_rejects_svg():
    # SVGs can carry active content — not accepted as an image source (S7).
    assert ImageParser().can_handle("https://example.com/diagram.svg") is False


class _FakeResponse:
    def __init__(self, content_type="image/png"):
        self.headers = {"content-type": content_type}


def _fake_safe_get(content, content_type="image/png"):
    def _inner(url, *, max_bytes, **kwargs):
        return content, _FakeResponse(content_type)

    return _inner


@pytest.mark.django_db
def test_download_attachments_stores_local_file(user, monkeypatch):
    note = Note.objects.create(
        owner=user, status=NoteStatus.DONE, source_type=SourceType.IMAGE
    )
    att = note.attachments.create(remote_url="https://example.com/pic.png", kind="image")

    monkeypatch.setattr(images, "safe_get", _fake_safe_get(b"\x89PNG\r\n\x1a\nfake-bytes"))

    stored = download_attachments(note)

    att.refresh_from_db()
    assert stored == 1
    assert att.file  # local file now set
    assert att.file.read() == b"\x89PNG\r\n\x1a\nfake-bytes"


@pytest.mark.django_db
def test_download_skips_non_image_content_type(user, monkeypatch):
    note = Note.objects.create(owner=user, status=NoteStatus.DONE)
    att = note.attachments.create(remote_url="https://example.com/notimg", kind="image")

    monkeypatch.setattr(images, "safe_get", _fake_safe_get(b"<html>", content_type="text/html"))

    stored = download_attachments(note)
    att.refresh_from_db()
    assert stored == 0
    assert not att.file  # remote_url stays as fallback


@pytest.mark.django_db
def test_download_blocks_svg_content_type(user, monkeypatch):
    note = Note.objects.create(owner=user, status=NoteStatus.DONE)
    att = note.attachments.create(remote_url="https://example.com/x", kind="image")

    monkeypatch.setattr(
        images, "safe_get", _fake_safe_get(b"<svg onload=alert(1)>", content_type="image/svg+xml")
    )
    assert download_attachments(note) == 0
    att.refresh_from_db()
    assert not att.file


@pytest.mark.django_db
def test_download_is_nonfatal_on_error(user, monkeypatch):
    note = Note.objects.create(owner=user, status=NoteStatus.DONE)
    note.attachments.create(remote_url="https://example.com/pic.png", kind="image")

    def boom(url, *, max_bytes, **kwargs):
        raise httpx.ConnectError("nope")

    monkeypatch.setattr(images, "safe_get", boom)
    assert download_attachments(note) == 0

    def unsafe(url, *, max_bytes, **kwargs):
        raise UnsafeURLError("internal host")

    monkeypatch.setattr(images, "safe_get", unsafe)
    assert download_attachments(note) == 0
