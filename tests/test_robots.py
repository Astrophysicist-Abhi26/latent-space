import pytest

import common as C
from offline import FakeHTTP, FakeResponse


class RobotsHTTP(FakeHTTP):
    def get(self, url, **kw):
        if url.endswith("/robots.txt"):
            return FakeResponse(url, 200, b"User-agent: *\nDisallow: /private\n", "text/plain")
        return FakeResponse(url, 200, b"<html>ok</html>", "text/html")


def test_robots_txt_is_respected_for_pages_not_feeds(monkeypatch):
    monkeypatch.setattr(C, "HTTP", RobotsHTTP(routes=[]))
    monkeypatch.setenv("LH_ROBOTS", "enforce")
    C.reset()
    assert C.get("https://example.org/public/jobs").status_code == 200
    with pytest.raises(C.RobotsDisallowed):
        C.get("https://example.org/private/jobs")
    assert C.get("https://example.org/private/feed.xml", feed=True).status_code == 200   # feeds are for programs
    monkeypatch.setenv("LH_ROBOTS", "report")
    assert C.get("https://example.org/private/jobs").status_code == 200
    assert C.ROBOTS_BLOCKED == ["https://example.org/private/jobs", "https://example.org/private/jobs"]
