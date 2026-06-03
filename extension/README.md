# Clip to Notes — browser extension

Clips the page you're looking at — in your normal, logged-in browser — into the
local source-to-notes app. Because it reads the already-rendered DOM from your
session, there's no server-side scraping, no bot-detection, and it works for X
posts/articles and any other page (paywalled, JS-heavy, login-required).

## Install (unpacked)

1. In the app, set a clip token in `.env` and restart:
   ```bash
   python -c "import secrets; print('CLIP_TOKEN=' + secrets.token_urlsafe(32))" >> .env
   docker compose up -d --force-recreate web worker
   ```
2. Chrome → `chrome://extensions` → enable **Developer mode** → **Load unpacked**
   → select this `extension/` folder.
3. Click the extension → **Settings** → set:
   - **Server URL**: `http://localhost:8000`
   - **Clip token**: the value of `CLIP_TOKEN` from your `.env`
   - **Save settings**

## Use

Browse to any page (an X post/article, a blog, etc.), click the extension, and
hit **Clip this page**. It extracts the title/text/images, POSTs to
`/api/clip/`, and the note appears on your dashboard (auto-summarized + tagged
when AI is on). For X, it targets tweet/article content specifically; elsewhere
it grabs the main article/`<main>`/body text plus images.

## How it talks to the app

`POST {server}/api/clip/` with header `Authorization: Bearer <token>` and JSON
`{ url, title, text, images[] }`. The endpoint is token-authenticated (not
session/CSRF), so it works cross-origin from any tab. The extension's
`host_permissions` are limited to `localhost`/`127.0.0.1`.
