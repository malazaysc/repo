"""Capture an authenticated X/Twitter session for the scraper.

Launches a *headed* Chromium, waits for you to log in to X manually, then saves
the browser ``storage_state`` (cookies + localStorage) to X_STORAGE_STATE_PATH.

Run this on your host (it needs a visible browser), not in a headless container:

    uv run python manage.py capture_x_session

The saved file contains live session credentials — it's gitignored; keep it secret.
"""
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Open a browser to log into X and save the authenticated session."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default=settings.X_STORAGE_STATE_PATH,
            help="Where to write the storage_state JSON (default: X_STORAGE_STATE_PATH).",
        )

    def handle(self, *args, **options):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise CommandError(
                "Playwright isn't installed. Install the 'browser' group "
                "(uv sync --group browser) and run `playwright install chromium`."
            ) from exc

        output = options["output"]
        os.makedirs(os.path.dirname(output), exist_ok=True)

        self.stdout.write(
            "Opening a browser. Log in to X, then return here and press Enter to save."
        )
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()
            page.goto("https://x.com/login")

            input("Press Enter once you're logged in and see your timeline... ")

            context.storage_state(path=output)
            browser.close()

        self.stdout.write(self.style.SUCCESS(f"Saved X session to {output}"))
        self.stdout.write("Set X_PARSER_ENABLED=1 to enable X ingestion.")
