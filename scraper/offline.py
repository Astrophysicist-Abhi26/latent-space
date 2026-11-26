"""
Offline mode: answer every request from tests/fixtures instead of the internet.

Used by the tests and by `python scraper/scrape.py --offline`, which builds a local
docs/jobs.json from the fixtures so the site can be previewed without network access
(that file is marked "sample" and is never used as the previous state of a real run).
"""

import json
import os
import re

import requests

import common as C

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "tests", "fixtures")

# (method, URL regex, fixture file or None for "404 Not Found"). First match wins.
ROUTES = [
    ("GET", r"hn\.algolia\.com/api/v1/search_by_date", "hn_search.json"),
    ("GET", r"hn\.algolia\.com/api/v1/items/", "hn_item.json"),
    ("GET", r"/robots\.txt$", None),
    ("GET", r"euraxess\.ec\.europa\.eu/jobs/search\?.*\bpage=\d", "empty.html"),
    ("GET", r"euraxess\.ec\.europa\.eu/jobs/search", "euraxess.html"),
    ("GET", r"nature\.com/naturecareers/jobsrss", "madgex_nature.xml"),
    ("GET", r"sciencecareers\.org/jobsrss", "madgex_science.xml"),
    ("GET", r"jobsrss", "empty_rss.xml"),
    ("GET", r"mpg\.de/feeds/jobs\.rss", "mpg.xml"),
    ("GET", r"jobrxiv\.org/\?feed=job_feed", "jobrxiv.xml"),
    ("GET", r"jobs\.ac\.uk/jobs/.*format=rss", "jobsacuk.xml"),
    ("GET", r"biotecnika\.org/category/jobs/feed", "biotecnika.xml"),
    ("GET", r"academicpositions\.com/jobs/position/post-doc/field/microbiology", "academicpositions.html"),
    ("GET", r"indiabioscience\.org/jobs", "indiabioscience.html"),
    ("GET", r"ncbs\.res\.in/jobportal", "ncbs.html"),
    ("GET", r"iisc\.ac\.in/careers/contract-project-staff", "iisc.html"),
    ("GET", r"thsti\.res\.in/public/en/Jobs", "thsti.html"),
    ("GET", r"boards-api\.greenhouse\.io/v1/boards/anthropic/", "greenhouse_anthropic.json"),
    ("GET", r"boards-api\.greenhouse\.io/v1/boards/isomorphiclabs/", "greenhouse_isomorphic.json"),
    ("GET", r"boards-api\.greenhouse\.io", "empty_jobs.json"),
    ("GET", r"api\.ashbyhq\.com/posting-api/job-board/tabulabio\b", "ashby_tabula.json"),
    ("GET", r"api\.ashbyhq\.com/posting-api/job-board/adaptyv\b", "ashby_adaptyv.json"),
    ("GET", r"api\.ashbyhq\.com", "empty_jobs.json"),
    ("GET", r"api\.(eu\.)?lever\.co/v0/postings/convergentresearch\b", "lever.json"),
    ("GET", r"api\.(eu\.)?lever\.co", "empty_list.json"),
    ("GET", r"apply\.workable\.com/api/v1/widget/accounts/labgenius\b", "workable.json"),
    ("GET", r"apply\.workable\.com", "empty_jobs.json"),
    ("POST", r"novartis\.wd3\.myworkdayjobs\.com/wday/cxs/.*/jobs$", "workday_list.json"),
    ("POST", r"myworkdayjobs\.com/wday/cxs/.*/jobs$", "workday_empty.json"),
    ("GET", r"myworkdayjobs\.com/wday/cxs/.*/job/", "workday_detail.json"),
    ("GET", r"api\.github\.com/repos/.+/issues", "github_issues.json"),
    ("GET", r"job_search|career|categories|/jobs", "empty.html"),
]
CTYPES = {"json": "application/json", "xml": "application/rss+xml; charset=utf-8", "html": "text/html; charset=utf-8"}


class FakeResponse:
    def __init__(self, url, status, body, ctype):
        self.url, self.status_code = url, status
        self.content = body if isinstance(body, bytes) else body.encode()
        self.headers = {"content-type": ctype}
        self.encoding = "utf-8"
        self.apparent_encoding = "utf-8"

    @property
    def text(self):
        return self.content.decode(self.encoding or "utf-8", "replace")

    def json(self):
        return json.loads(self.content)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} for {self.url}", response=self)


class FakeHTTP:
    """Stands in for common.HTTP (a requests.Session)."""

    def __init__(self, routes=None, fixtures=FIXTURES):
        self.routes = routes or ROUTES
        self.fixtures = fixtures
        self.calls = []

    def _answer(self, method, url):
        self.calls.append((method, url))
        for m, rx, name in self.routes:
            if m == method and re.search(rx, url):
                if name is None:
                    return FakeResponse(url, 404, b"", "text/plain")
                with open(os.path.join(self.fixtures, name), "rb") as f:
                    return FakeResponse(url, 200, f.read(), CTYPES[name.rsplit(".", 1)[-1]])
        raise requests.ConnectionError(f"offline: no fixture for {method} {url}")

    def get(self, url, **kw):
        return self._answer("GET", url)

    def post(self, url, **kw):
        return self._answer("POST", url)


def install():
    """Route all of common.HTTP to the fixtures (offline runs)."""
    fake = FakeHTTP()
    C.HTTP = fake
    C.HOST_GAP = 0
    C.reset()
    os.environ.setdefault("LH_TODAY", "2026-11-24")
    os.environ.setdefault("GITHUB_REPOSITORY", "example/latent-space")
    return fake
