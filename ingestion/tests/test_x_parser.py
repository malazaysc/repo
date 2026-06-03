import pytest
from django.test import override_settings

from ingestion.browser import x_scraper
from ingestion.parsers import ParserError
from ingestion.parsers.x import XParser
from notes.models import SourceType


@pytest.mark.parametrize(
    "url,handled",
    [
        ("https://x.com/jack/status/20", True),
        ("https://twitter.com/jack/status/20", True),
        ("https://mobile.twitter.com/jack/status/20", True),
        ("https://example.com/jack", False),
        ("https://youtube.com/watch?v=x", False),
    ],
)
def test_x_can_handle(url, handled):
    assert XParser().can_handle(url) is handled


@override_settings(X_PARSER_ENABLED=False)
def test_parse_disabled_raises_friendly_error():
    with pytest.raises(ParserError, match="X capture is disabled"):
        XParser().parse("https://x.com/jack/status/20")


@override_settings(X_PARSER_ENABLED=True, X_STORAGE_STATE_PATH="/nonexistent/state.json")
def test_parse_without_session_raises():
    with pytest.raises(ParserError, match="No saved X session"):
        XParser().parse("https://x.com/jack/status/20")


def test_parse_success_with_mocked_browser(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    state.write_text("{}")

    def fake_scrape(url, *, storage_state_path, headless=True, timeout_ms=30000):
        assert storage_state_path == str(state)
        return {
            "title": "Hello world",
            "text": "Hello world\n\nthis is a tweet",
            "images": ["https://pbs.twimg.com/media/abc.jpg"],
            "metadata": {"author": "Jack"},
        }

    monkeypatch.setattr(x_scraper, "scrape_x", fake_scrape)

    with override_settings(X_PARSER_ENABLED=True, X_STORAGE_STATE_PATH=str(state)):
        result = XParser().parse("https://x.com/jack/status/20")

    assert result.source_type == SourceType.X
    assert result.title == "Hello world"
    assert "this is a tweet" in result.text
    assert result.metadata["author"] == "Jack"
    assert result.images[0].url == "https://pbs.twimg.com/media/abc.jpg"


def test_scrape_x_raises_without_playwright(monkeypatch):
    # Simulate Playwright not installed.
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("playwright"):
            raise ImportError("no playwright")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(x_scraper.XScrapeError, match="Playwright isn't installed"):
        x_scraper.scrape_x("https://x.com/x/status/1", storage_state_path=None)
