import datetime as dt
import os
import re

import yaml

import scrape as S
import taxonomy as T
from geo import COUNTRIES
from sources_ats import ADAPTERS, GROUP_SECTOR
from sources_feeds import PARSERS

SC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scraper")


def load(name):
    with open(os.path.join(SC, name), encoding="utf-8") as f:
        return yaml.safe_load(f)


def _common(s):
    for key in ("include", "exclude", "skip_if", "href_filter", "href", "org_from_href"):
        if s.get(key):
            re.compile(s[key])
    for t in s.get("topics") or []:
        assert t in T.NODES, t
    if s.get("country"):
        assert s["country"] in COUNTRIES, s["country"]


def test_sources_yaml():
    for s in load("sources.yaml")["sources"]:
        assert s["type"] in ("rss", "euraxess", "links", "hn"), s["name"]
        urls = s.get("urls") or [s.get("url")]
        assert urls and all(u.startswith("https://") for u in urls), s["name"]
        if s["type"] == "rss":
            assert s.get("parser", "generic") in PARSERS
        if any("{q}" in u for u in urls):
            assert s.get("queries"), s["name"]
        assert "verified" in s, s["name"]
        _common(s)


def test_institutes_yaml():
    for s in load("institutes.yaml")["sources"]:
        assert (s.get("url") or s.get("urls")) and "verified" in s
        _common(s)


def test_companies_yaml():
    for c in load("companies.yaml")["companies"]:
        assert c["ats"] in ADAPTERS and c.get("group") in GROUP_SECTOR, c["name"]
        assert isinstance(c.get("verified"), bool), c["name"]
        if c["ats"] == "workday":
            assert c.get("host") and c.get("tenant") and c.get("site") and c.get("queries"), c["name"]
        else:
            assert re.fullmatch(r"[a-z0-9-]+", c["slug"]), c["name"]


def test_programmes_yaml():
    ids = set()
    for f in load("programmes.yaml")["programmes"]:
        assert f["id"] not in ids and f["url"].startswith("https://"), f["id"]
        assert f["region"] in ("europe", "india", "global", "north-america", "asia-pacific"), f["id"]
        assert f["kind"] in ("mtech", "residency", "internship"), f["id"]
        assert f["kind"] != "internship" or f.get("area") in ("india", "abroad"), f["id"]
        ids.add(f["id"])
        for w in f.get("windows") or []:
            assert isinstance(w["deadline"], dt.date) and w.get("checked")
            assert "opens" not in w or (isinstance(w["opens"], dt.date) and w["opens"] < w["deadline"])


def test_source_names_are_unique():
    names = [s.name for s in S.build_sources(include_disabled=True)]
    assert len(names) == len(set(names))
