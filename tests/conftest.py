import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scraper"))

# Tests never touch the network: requests go to tests/fixtures through offline.FakeHTTP.
os.environ.setdefault("LH_TODAY", "2026-11-24")
os.environ.setdefault("LH_ROBOTS", "off")          # robots.txt has its own test (test_robots.py)
os.environ.setdefault("LH_HOST_GAP", "0")
os.environ.setdefault("LH_NO_ENRICH", "1")

import pytest  # noqa: E402


@pytest.fixture
def fake_http(monkeypatch):
    import common as C
    import offline
    fake = offline.FakeHTTP()
    monkeypatch.setattr(C, "HTTP", fake)
    monkeypatch.setattr(C, "HOST_GAP", 0)
    C.reset()
    monkeypatch.setenv("GITHUB_REPOSITORY", "example/latent-space")
    return fake
