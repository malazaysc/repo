import pytest

from ingestion.parsers import get_parser
from ingestion.parsers.youtube import extract_video_id
from notes.models import SourceType


@pytest.mark.parametrize(
    "url,expected_name,expected_type",
    [
        ("https://youtu.be/dQw4w9WgXcQ", "youtube", SourceType.YOUTUBE),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "youtube", SourceType.YOUTUBE),
        ("https://x.com/jack/status/20", "x", SourceType.X),
        ("https://twitter.com/jack/status/20", "x", SourceType.X),
        ("https://en.wikipedia.org/wiki/Web_scraping", "article", SourceType.ARTICLE),
        ("https://example.com/some/post", "article", SourceType.ARTICLE),
        ("https://example.com/photo.JPG", "image", SourceType.IMAGE),
        ("https://cdn.example.com/a/b/pic.png?w=200", "image", SourceType.IMAGE),
        # .svg is no longer an image source (S7) — falls through to article.
        ("https://example.com/diagram.svg", "article", SourceType.ARTICLE),
        # Look-alike YouTube host must not route to the YouTube parser (S4).
        ("https://youtube.com.evil.com/watch?v=dQw4w9WgXcQ", "article", SourceType.ARTICLE),
    ],
)
def test_get_parser_routes_by_url(url, expected_name, expected_type):
    parser = get_parser(url)
    assert parser.name == expected_name
    assert parser.source_type == expected_type


@pytest.mark.parametrize(
    "url,vid",
    [
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10s", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/abc12345678", "abc12345678"),
        ("https://example.com/not-a-video", None),
    ],
)
def test_extract_video_id(url, vid):
    assert extract_video_id(url) == vid
