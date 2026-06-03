import pytest
from django.urls import reverse

from notes.models import Note, NoteStatus, SourceType

pytestmark = pytest.mark.django_db


def _make_note(user, title, text, summary=""):
    note = Note.objects.create(
        owner=user,
        title=title,
        cleaned_text=text,
        summary=summary,
        source_type=SourceType.ARTICLE,
        status=NoteStatus.DONE,
    )
    note.update_search_vector()
    return note


def test_fulltext_search_matches_content(auth_client, user):
    _make_note(user, "Django ORM tips", "Using querysets efficiently with select_related")
    _make_note(user, "Cooking pasta", "Boil water and add salt")

    resp = auth_client.get(reverse("notes:dashboard"), {"q": "querysets"})
    content = resp.content.decode()
    assert "Django ORM tips" in content
    assert "Cooking pasta" not in content


def test_fulltext_search_ranks_title_above_body(auth_client, user):
    # "python" in the body of one, in the title of the other.
    _make_note(user, "Snakes of the world", "a python is a large snake")
    _make_note(user, "Python programming", "general notes about coding")

    resp = auth_client.get(reverse("notes:dashboard"), {"q": "python"})
    body = resp.content.decode()
    # Both match; the title hit (weight A) should appear before the body hit.
    assert body.index("Python programming") < body.index("Snakes of the world")


def test_search_websearch_quoted_phrase(auth_client, user):
    _make_note(user, "Note A", "machine learning models are useful")
    _make_note(user, "Note B", "learning to cook machine washable fabrics")

    resp = auth_client.get(reverse("notes:dashboard"), {"q": '"machine learning"'})
    content = resp.content.decode()
    assert "Note A" in content
    assert "Note B" not in content


def test_pagination_limits_per_page(auth_client, user):
    for i in range(15):
        _make_note(user, f"Note {i:02d}", "body text")

    resp = auth_client.get(reverse("notes:dashboard"))
    page = resp.context["page"]
    assert page.paginator.count == 15
    assert page.paginator.num_pages == 2
    assert len(page.object_list) == 12

    resp2 = auth_client.get(reverse("notes:dashboard"), {"page": 2})
    assert len(resp2.context["page"].object_list) == 3
