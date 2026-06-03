# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A personal "source-to-notes" app: submit a URL (YouTube, article/link, bare image, X/Twitter) or paste text, and a background worker scrapes/parses it into a searchable `Note`, optionally summarized by Claude. Django 6 + HTMX + Alpine.js + PicoCSS, Postgres, Celery + Redis, managed with `uv`. Single-user.

**Dependency philosophy:** track the latest. Avoid upper-bound version caps; prefer the newest stable runtime/framework; Dependabot opens weekly update PRs — merging them when CI is green is expected.

## Commands

The app runs in Docker; tests run on the host against the dockerized Postgres (port-mapped to localhost).

```bash
# Run the stack (web, worker, db, redis)
docker compose up --build -d
docker compose exec web python manage.py bootstrap_user   # creates admin/admin in DEBUG
# → http://localhost:8000  (login admin/admin)

# Tests — REQUIRE Postgres (full-text search is Postgres-only). Point DATABASE_URL at the
# dockerized db on localhost; pytest-django creates an isolated test_* database.
DATABASE_URL=postgres://repo:repo@localhost:5432/repo uv run pytest
DATABASE_URL=postgres://repo:repo@localhost:5432/repo uv run pytest path/to/test_x.py::test_name   # single test

# Lint (must be clean; CI enforces it)
uv run ruff check .

# Dependencies
uv sync                  # main + dev groups (no 'browser' group)
uv lock --upgrade        # bump everything to latest, then re-test

# Migrations (use test settings locally — dev settings need debug_toolbar + DEBUG)
DJANGO_SETTINGS_MODULE=config.settings.test DATABASE_URL=postgres://repo:repo@localhost:5432/repo \
  uv run python manage.py makemigrations

# Inside containers, code is volume-mounted but Celery caches imports: restart the worker
# after changing parser/task code:  docker compose restart worker
```

CI (`.github/workflows/ci.yml`) runs ruff + the full pytest suite against a Postgres service on every push/PR.

## Architecture

**Ingestion is the core.** Flow: a view creates a `Note(status=pending)` and dispatches the `ingest_note` Celery task; the HTMX note card polls `/notes/<id>/status/` and swaps itself in when the worker finishes. Read these together to understand a change to ingestion:

- `ingestion/tasks.py` — `ingest_note` orchestrates: resolve parser → parse → download images → AI → mark done. **Retry policy matters:** only `_TRANSIENT_ERRORS` (network) are retried; `ParserError` and deterministic bugs fail fast. The resolved `source_type` is persisted *before* parsing so a failed note still shows the right badge.
- `ingestion/parsers/` — **strategy + registry pattern.** `registry.py` resolves a URL to the first matching `BaseParser` (order = priority: youtube → x → image → article-as-fallback). **Adding a source = one `BaseParser` subclass + one line in the registry.** Every parser returns a normalized `ParsedContent`. `can_handle` uses `urlparse().hostname` exact-match (never substring — that's a security boundary for the X scraper).
- `ingestion/net.py` — **all server-side fetches of user URLs MUST go through `safe_get`/`safe_get_text`** (SSRF guard: blocks non-http(s) and private/loopback/metadata IPs, validates each redirect hop, caps body size). Don't call `httpx.get` directly on user-supplied URLs.
- `ingestion/browser/x_scraper.py` + `parsers/x.py` — X is scraped via Playwright using a saved authenticated `storage_state`. Opt-in: `X_PARSER_ENABLED=1`, `INSTALL_BROWSERS=1` (bakes Chromium into the worker image), and a session captured via `manage.py capture_x_session`. Host is asserted against `X_HOSTS` before driving the authenticated browser.
- `ingestion/ai/client.py` — pluggable Claude summarization (`summarize` for text, `describe_image` for vision/OCR). **Fails soft:** returns `None` when disabled/no-key/refusal so notes ingest without a summary; non-JSON replies are never stored as note body. Off unless `AI_SUMMARY_ENABLED=1` + `ANTHROPIC_API_KEY`. Defaults to `claude-haiku-4-5` with prompt caching on the system prompt already wired.

**Search:** `Note.search_vector` is a Postgres `SearchVectorField` (GIN-indexed), recomputed via `note.update_search_vector()` after ingest and edit. The dashboard uses `SearchQuery(..., search_type="websearch")` + `SearchRank` (weighted title > summary > body). This is why tests need real Postgres.

**Settings** are split in `config/settings/`: `base` → `dev` (DEBUG, conditional debug-toolbar), `prod` (enforces a real `SECRET_KEY`, explicit `ALLOWED_HOSTS`, security headers), `test` (Postgres + eager Celery + fast hashing + plain static storage). `manage.py`/wsgi default to `config.settings.dev`; pytest uses `config.settings.test`.

**Models** (`notes/models.py`): `Note` (owner-scoped — all views filter through `_user_notes(request)` before `get_object_or_404`, so no IDOR), `Tag` (M2M, auto-created from AI tags), `Attachment` (image stored locally via `ingestion/images.py:download_attachments`, with `remote_url` kept as fallback).

## Conventions

- Templates render scraped/AI content with autoescaping (no `|safe`/`mark_safe`) — keep it that way.
- HTMX *mutation* endpoints (`add_source`/`edit`/`delete`/`retry`) are `@require_POST` + `@login_required`; the status-poll endpoint is `@require_GET` + `@login_required`. The base template sends the CSRF token via `hx-headers`.
- SVG is intentionally excluded from accepted image types (active-content/XSS risk).
- Don't store large blobs you won't read back (article `raw_content` is deliberately empty); use `save(update_fields=[...])` on targeted writes in the ingest path.
