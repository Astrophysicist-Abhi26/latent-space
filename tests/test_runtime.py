"""A slow or stuck website must never stall the daily run."""
import time

from urllib3.response import HTTPResponse

import common as C
import scrape as S


class FakeSource:
    def __init__(self, name):
        self.name, self.group, self.kind, self.verified, self.verification, self.url, self.cfg = name, "g", "rss", True, "", "", {}


def test_a_stuck_source_is_skipped_not_waited_for(monkeypatch):
    def fake_run_one(src):
        if src.name == "stuck":
            time.sleep(30)                       # e.g. a site that says "come back later" and never answers
        return src, [{"id": src.name}], "ok", None, 0.0
    monkeypatch.setattr(S, "run_one", fake_run_one)
    t0 = time.monotonic()
    raw, health = S.run_sources([FakeSource("a"), FakeSource("stuck"), FakeSource("b")], [], workers=2, deadline_s=1)
    assert time.monotonic() - t0 < 4
    status = {h["name"]: h["status"] for h in health}
    assert status == {"a": "ok", "stuck": "error", "b": "ok"}
    assert [j["id"] for j in raw] == ["a", "b"]
    assert "skipped today" in next(h["error"] for h in health if h["name"] == "stuck")


def test_retry_after_is_capped():
    r = HTTPResponse(body=b"", headers={"Retry-After": "3600"}, status=429)
    assert C.CappedRetry(total=3).get_retry_after(r) == C.RETRY_AFTER_CAP


def test_call_with_deadline():
    assert C.call_with_deadline(2, lambda x: x * 2, 21) == 42
    t0 = time.monotonic()
    try:
        C.call_with_deadline(0.3, time.sleep, 10)
        raise AssertionError("should have timed out")
    except TimeoutError:
        assert time.monotonic() - t0 < 2
