import pytest

from ingestion.parsers import ParserError
from ingestion.parsers.x import XParser


@pytest.mark.parametrize(
    "url,handled",
    [
        ("https://x.com/jack/status/20", True),
        ("https://twitter.com/jack/status/20", True),
        ("https://mobile.twitter.com/jack/status/20", True),
        ("https://example.com/jack", False),
        ("https://youtube.com/watch?v=x", False),
        # Look-alike / spoofed hosts must NOT match.
        ("https://x.com.evil.com/jack", False),
        ("https://evil.com/?u=//x.com/jack", False),
        ("https://notx.com/jack", False),
    ],
)
def test_x_can_handle(url, handled):
    assert XParser().can_handle(url) is handled


def test_x_parse_points_to_extension():
    # X can't be fetched server-side; the parser tells the user to use the clipper.
    with pytest.raises(ParserError, match="Clip to Notes"):
        XParser().parse("https://x.com/jack/status/20")
