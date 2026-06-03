from django.contrib.auth.decorators import login_required
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.core.paginator import Paginator
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from .forms import AddSourceForm, NoteEditForm
from .models import Note, NoteStatus, SourceType, Tag

NOTES_PER_PAGE = 12


def _user_notes(request):
    return Note.objects.filter(owner=request.user)


@login_required
def dashboard(request):
    notes = _user_notes(request).prefetch_related("tags")

    query = request.GET.get("q", "").strip()
    if query:
        # Postgres full-text search; "websearch" tolerates quotes/AND/OR/- syntax.
        search_query = SearchQuery(query, search_type="websearch")
        notes = (
            notes.filter(search_vector=search_query)
            .annotate(rank=SearchRank(F("search_vector"), search_query))
            .order_by("-rank", "-created_at")
        )

    tag_slug = request.GET.get("tag", "").strip()
    if tag_slug:
        notes = notes.filter(tags__slug=tag_slug)

    paginator = Paginator(notes, NOTES_PER_PAGE)
    page = paginator.get_page(request.GET.get("page"))

    context = {
        "form": AddSourceForm(),
        "page": page,
        "notes": page.object_list,
        "tags": Tag.objects.filter(notes__owner=request.user).distinct(),
        "query": query,
        "active_tag": tag_slug,
    }
    return render(request, "notes/dashboard.html", context)


@login_required
@require_POST
def add_source(request):
    from ingestion.tasks import ingest_note

    form = AddSourceForm(request.POST)
    if not form.is_valid():
        return render(request, "notes/_add_form.html", {"form": form}, status=422)

    data = form.cleaned_data
    if data["source_url"]:
        fields = {"source_url": data["source_url"], "title": data["title"]}
    else:
        # Manual text note — no fetching needed; ingest task still summarizes.
        fields = {
            "title": data["title"],
            "source_type": SourceType.TEXT,
            "raw_content": data["text"],
            "cleaned_text": data["text"],
        }

    note = Note.objects.create(owner=request.user, status=NoteStatus.PENDING, **fields)
    ingest_note.delay(note.pk)

    # Return the new card; HTMX prepends it and the form resets client-side.
    return render(request, "notes/_card.html", {"note": note})


@login_required
@require_GET
def note_status(request, pk):
    """Polled by HTMX while a note is being ingested."""
    note = get_object_or_404(_user_notes(request), pk=pk)
    return render(request, "notes/_card.html", {"note": note})


@login_required
def note_detail(request, pk):
    note = get_object_or_404(_user_notes(request).prefetch_related("tags", "attachments"), pk=pk)
    return render(request, "notes/detail.html", {"note": note})


@login_required
@require_POST
def note_edit(request, pk):
    note = get_object_or_404(_user_notes(request), pk=pk)
    form = NoteEditForm(request.POST, instance=note)
    if form.is_valid():
        form.save()
        note.update_search_vector()
        return redirect(note.get_absolute_url())

    # Invalid — re-render the detail page with the editor open and errors shown.
    return render(
        request,
        "notes/detail.html",
        {"note": note, "edit_form": form, "open_editor": True},
        status=422,
    )


@login_required
@require_POST
def note_delete(request, pk):
    note = get_object_or_404(_user_notes(request), pk=pk)
    note.delete()
    if request.headers.get("HX-Request"):
        return render(request, "notes/_deleted.html", {})
    return redirect("notes:dashboard")


@login_required
@require_POST
def note_retry(request, pk):
    from ingestion.tasks import ingest_note

    note = get_object_or_404(_user_notes(request), pk=pk)
    note.status = NoteStatus.PENDING
    note.error_message = ""
    note.save(update_fields=["status", "error_message", "updated_at"])
    ingest_note.delay(note.pk)
    return render(request, "notes/_card.html", {"note": note})
