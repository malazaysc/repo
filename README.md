# Repo — source-to-notes

Parse/scrape content from various sources and store it as searchable notes.

- **Sources:** YouTube (multi-language transcripts), generic links/articles
  (text + images), bare image links, pasted text, and X/Twitter (via an
  authenticated headless browser — see below).
- **AI:** optional Claude-generated summary, highlights, and tags on ingest
  (text sources are summarized; image sources are captioned + OCR'd via vision).
  Tags populate the dashboard tag filter.
- **Stack:** Django 6 · HTMX · Alpine.js · PicoCSS · Postgres · Celery + Redis
  · Python 3.14 · uv. Dependencies track latest (Dependabot keeps them current).

## Quick start (Docker)

```bash
cp .env.example .env            # then set DJANGO_SECRET_KEY, optionally ANTHROPIC_API_KEY
docker compose up --build       # starts db, redis, web, worker
```

In another shell, create the login user:

```bash
docker compose exec web python manage.py bootstrap_user   # admin / admin by default
```

Open http://localhost:8000 and log in.

To enable AI summaries: set `ANTHROPIC_API_KEY` and `AI_SUMMARY_ENABLED=1` in `.env`,
then `docker compose up -d`.

## How ingestion works

1. You submit a URL (or paste text) on the dashboard.
2. A `Note` is created (`pending`) and a Celery task is dispatched; the card
   HTMX-polls its status.
3. The worker picks a parser via the registry, extracts content, optionally
   summarizes with Claude, and marks the note `done` (or `failed`, with retry).

## Enabling X / Twitter

X has no free API and blocks anonymous scraping, so ingestion drives a headless
Chromium loaded with *your* authenticated session.

1. Bake the browser into the worker image:
   ```bash
   echo "INSTALL_BROWSERS=1" >> .env
   docker compose build worker
   ```
2. Capture your session (run on your host — it opens a real browser window):
   ```bash
   uv sync --group browser && uv run playwright install chromium
   uv run python manage.py capture_x_session     # log in, press Enter
   ```
   This writes `secrets/x_storage_state.json` (gitignored — it holds live
   credentials). Mount/copy it where the worker can read `X_STORAGE_STATE_PATH`.
3. Turn it on: set `X_PARSER_ENABLED=1` in `.env`, then `docker compose up -d`.

Until then, X links fail with a friendly message and you can "paste text instead".

## Search

Dashboard search uses Postgres full-text search (weighted title > summary >
content, `websearch` syntax so quotes/`OR`/`-` work). The note list is paginated.

## Testing

```bash
docker compose up -d db                 # tests need Postgres
DATABASE_URL=postgres://repo:repo@localhost:5432/repo uv run pytest
```

## Adding a new source

Implement a `BaseParser` subclass in `ingestion/parsers/` (`can_handle` +
`parse` → `ParsedContent`) and register it in `ingestion/parsers/registry.py`.
The X parser (`ingestion/parsers/x.py`) is a documented stub for the planned
authenticated-browser approach.

## Project layout

```
config/        settings (base/dev/prod), celery, urls
core/          base templates, static, bootstrap_user command
notes/         Note/Tag/Attachment models, views, HTMX templates
ingestion/     parser registry + parsers, AI client, Celery tasks
```

## Local dev without Docker

```bash
uv sync
# point DATABASE_URL / CELERY_* at local services, then:
uv run python manage.py migrate
uv run python manage.py bootstrap_user
uv run python manage.py runserver
uv run celery -A config worker -l info   # separate shell
```
