import pytest
from django.urls import reverse

from notes.models import Note, NoteStatus, SourceType

pytestmark = pytest.mark.django_db


def test_dashboard_requires_login(client):
    resp = client.get(reverse("notes:dashboard"))
    assert resp.status_code == 302
    assert "/accounts/login/" in resp["Location"]


def test_dashboard_loads_for_user(auth_client):
    resp = auth_client.get(reverse("notes:dashboard"))
    assert resp.status_code == 200


def test_notes_are_owner_scoped(auth_client, user, django_user_model):
    other = django_user_model.objects.create_user("other", password="pw")
    Note.objects.create(owner=user, title="mine", status=NoteStatus.DONE)
    Note.objects.create(owner=other, title="theirs", status=NoteStatus.DONE)

    resp = auth_client.get(reverse("notes:dashboard"))
    content = resp.content.decode()
    assert "mine" in content
    assert "theirs" not in content


def test_detail_renders_note_with_remote_image(auth_client, user):
    note = Note.objects.create(
        owner=user, title="With image", status=NoteStatus.DONE, source_type=SourceType.YOUTUBE
    )
    note.attachments.create(remote_url="https://example.com/thumb.jpg", kind="image")

    resp = auth_client.get(reverse("notes:detail", args=[note.pk]))
    assert resp.status_code == 200
    assert "https://example.com/thumb.jpg" in resp.content.decode()
