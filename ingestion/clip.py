"""Clip endpoint: receives page content from the browser extension.

The extension reads the rendered page in the user's logged-in session and POSTs
it here, so there's no server-side fetch (no scraping, SSRF, or bot-detection).
Authenticated by a shared bearer token (``CLIP_TOKEN``), not the session, so the
extension can call it cross-origin from any page.
"""
from __future__ import annotations

import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.utils.crypto import constant_time_compare
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from notes.models import Attachment, Note, NoteStatus, SourceType

from .parsers import get_parser
from .tasks import ingest_note


def _detect_source_type(url: str) -> str:
    if not url:
        return SourceType.TEXT
    try:
        return get_parser(url).source_type
    except Exception:
        return SourceType.ARTICLE


def _token_ok(request) -> bool:
    auth = request.headers.get("Authorization", "")
    provided = auth[7:] if auth.startswith("Bearer ") else request.headers.get("X-Clip-Token", "")
    return bool(provided) and constant_time_compare(provided, settings.CLIP_TOKEN)


@csrf_exempt
@require_POST
def clip(request):
    if not settings.CLIP_TOKEN:
        return JsonResponse({"error": "clip endpoint disabled; set CLIP_TOKEN"}, status=503)
    if not _token_ok(request):
        return JsonResponse({"error": "invalid or missing token"}, status=403)

    try:
        data = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid JSON"}, status=400)

    url = (data.get("url") or "").strip()
    title = (data.get("title") or "").strip()[:500]
    text = (data.get("text") or "").strip()
    images = data.get("images") or []
    if not text and not url:
        return JsonResponse({"error": "nothing to clip (need text or url)"}, status=400)

    owner = get_user_model().objects.filter(is_superuser=True).order_by("pk").first()
    if owner is None:
        return JsonResponse({"error": "no owner user configured"}, status=500)

    note = Note.objects.create(
        owner=owner,
        source_url=url[:2000],
        title=title,
        source_type=_detect_source_type(url),
        raw_content=text,
        cleaned_text=text,
        status=NoteStatus.PENDING,
    )
    for img_url in images[:12]:
        if isinstance(img_url, str) and img_url.startswith(("http://", "https://")):
            note.attachments.create(remote_url=img_url[:2000], kind=Attachment.Kind.IMAGE)

    ingest_note.delay(note.pk)

    return JsonResponse(
        {
            "id": note.pk,
            "status": note.status,
            "url": request.build_absolute_uri(note.get_absolute_url()),
        },
        status=201,
    )
