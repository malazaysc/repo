import pytest

from ingestion import net
from ingestion.net import UnsafeURLError, assert_safe_url, safe_get


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/x",
        "file:///etc/passwd",
        "http://localhost/admin",
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata
        "http://[::1]/",
        "http://db:5432/",  # docker-internal service name resolving privately
    ],
)
def test_assert_safe_url_blocks_internal_and_bad_schemes(url, monkeypatch):
    # Force internal-looking hostnames to resolve to a private IP.
    def fake_getaddrinfo(host, *a, **k):
        mapping = {
            "localhost": "127.0.0.1",
            "db": "10.0.0.5",
        }
        ip = mapping.get(host, host)
        return [(2, 1, 6, "", (ip, 0))]

    monkeypatch.setattr(net.socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(UnsafeURLError):
        assert_safe_url(url)


def test_assert_safe_url_allows_public(monkeypatch):
    monkeypatch.setattr(net.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))])
    assert_safe_url("https://example.com/page")  # no raise


def test_safe_get_enforces_size_cap(monkeypatch):
    monkeypatch.setattr(net.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))])

    class _Resp:
        is_redirect = False

        def raise_for_status(self):
            pass

        def iter_bytes(self):
            yield b"x" * 10
            yield b"y" * 10

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _Client:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def stream(self, method, url):
            return _Resp()

    monkeypatch.setattr(net.httpx, "Client", _Client)
    with pytest.raises(UnsafeURLError, match="exceeds"):
        safe_get("https://example.com/big", max_bytes=15)
