#!/usr/bin/env python3
"""
Latent Space — daily pipeline.

  sources: feeds, EURAXESS, job-link boards, institute pages, company job boards,
           watchlist and "Add a position" issues
  -> health check (+ a broken source keeps its last good postings for a few days)
  -> normalise -> de-duplicate -> classify -> drop expired / stale / PhD / off-topic
  -> read the detail pages of short, promising postings -> CV match
  -> optional Claude fit check -> score once per research profile
  -> docs/jobs.json (+ notify/digest.md for the daily digest issue)

Run locally
  python scraper/scrape.py                    every source (5-15 minutes: one request per host per second)
  python scraper/scrape.py --only EURAXESS    sources whose name contains a word
  python scraper/scrape.py --offline          no network: builds docs/jobs.json from tests/fixtures
Environment
  ANTHROPIC_API_KEY  enables the Claude fit check (llm_fit.py)
  LH_NO_ENRICH=1     skip detail pages;  LH_ENRICH_MAX  how many per run (default 50)
  LH_TODAY           pin "today" (YYYY-MM-DD) for reproducible runs
"""

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import os
import threading
import queue
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml                                                         # noqa: E402
from bs4 import BeautifulSoup                                       # noqa: E402

import classify as K                                                # noqa: E402
import common as C                                                  # noqa: E402
import cvmatch                                                      # noqa: E402
import llm_fit                                                      # noqa: E402
import profiles as P                                                # noqa: E402
import taxonomy as T                                                # noqa: E402
from geo import COUNTRIES, REGIONS                                  # noqa: E402
from sources_ats import fetch_company                               # noqa: E402
from sources_feeds import fetch_rss, fetch_hn_hiring                # noqa: E402
from sources_manual import fetch_issues, fetch_watchlist            # noqa: E402
from sources_web import fetch_euraxess, fetch_links, fetch_listing  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "docs", "jobs.json")
NOTIFY = os.path.join(ROOT, "notify")
CACHE_DIR = os.path.join(HERE, "cache")
SITE = K.SITE
CV_FILE = os.path.join(HERE, SITE.get("cv", "cv/kartik.txt"))

MAX_AGE_DAYS = 75          # a posting without a deadline is dropped this long after it was posted
MAX_JOBS = 3000
SOURCE_DEADLINE_S = int(os.environ.get("LH_SOURCE_DEADLINE", "600"))   # a source still silent after this is skipped today
ENRICH_BUDGET_S = 300     # seconds spent reading detail pages per run, at most
CARRY_MAX_DAYS = 10        # a broken source keeps its last good postings this long
SUMMARY_CHARS = 320
DIGEST_MIN = 55            # the digest lists new postings scoring at least this (default profile)
ENRICH_MAX = int(os.environ.get("LH_ENRICH_MAX", "50"))
BAD = ("error", "robots", "empty", "unverified")
COMPANY_GROUPS = {"ai-bio": "AI × biology companies", "pharma": "Pharma & diagnostics"}
ATS_PAGES = {"greenhouse": "https://job-boards.greenhouse.io/{slug}", "lever": "https://jobs.lever.co/{slug}",
             "ashby": "https://jobs.ashbyhq.com/{slug}", "workable": "https://apply.workable.com/{slug}/"}
OUT_KEYS = ("id", "title", "org", "location", "country", "region", "remote", "url", "apply", "source", "sources",
            "posted", "deadline", "first_seen", "kind", "sector", "lab", "coding", "level", "phd", "needs_phd", "visa", "topics",
            "cv", "llm", "pinned", "issue", "carried")


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------
def load_yaml(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class Source:
    def __init__(self, name, fn, cfg, group, kind):
        self.name, self.fn, self.cfg, self.group, self.kind = name, fn, cfg, group, kind
        v = str(cfg.get("verified", True)).strip().lower()
        self.verification = ("to confirm" if v.startswith(("no", "false")) else
                             "partly confirmed" if v.startswith("partly") else "confirmed")
        self.verified = self.verification == "confirmed"      # a failing unconfirmed source shows amber, not red
        self.min_expected = int(cfg.get("min_expected", 1))
        self.enabled = cfg.get("enabled", True) is not False

    @property
    def url(self):
        c = self.cfg
        if c.get("url"):
            return c["url"].replace("{q}", "…")
        if c.get("urls"):
            return c["urls"][0]
        if c.get("ats") == "workday":
            return f"https://{c['host']}/{c['site']}"
        if c.get("ats") in ATS_PAGES:
            return ATS_PAGES[c["ats"]].format(**c)
        return ""


def build_sources(include_disabled=False):
    types = {"rss": fetch_rss, "euraxess": fetch_euraxess, "links": fetch_links, "hn": fetch_hn_hiring}
    out = [Source(s["name"], types[s["type"]], s, s.get("group", "Other"), s["type"])
           for s in load_yaml("sources.yaml").get("sources", [])]
    out += [Source(s["name"], fetch_listing, s, s.get("group", "Institutes"), "listing")
            for s in load_yaml("institutes.yaml").get("sources", [])]
    # a company with no biology opening today is healthy: only a failing board is an error
    out += [Source(c["name"], fetch_company, {"min_expected": 0, **c},
                   COMPANY_GROUPS.get(c.get("group"), "Biotech & research organisations"), c["ats"])
            for c in load_yaml("companies.yaml").get("companies", [])]
    out.append(Source("Watchlist", lambda cfg: fetch_watchlist(), {"min_expected": 0}, "Added by hand", "manual"))
    out.append(Source("Added by you", lambda cfg: fetch_issues(), {"min_expected": 0}, "Added by hand", "manual"))
    return out if include_disabled else [s for s in out if s.enabled]


def run_one(src):
    t0 = time.monotonic()
    try:
        batch = src.fn(src.cfg)
        error = ""
        if not batch:
            status = "ok" if src.min_expected == 0 else "empty"
        elif len(batch) < src.min_expected:
            status = "low"
        else:
            status = "ok"
    except C.RobotsDisallowed as e:
        batch, status, error = [], "robots", str(e)
    except Exception as e:                                           # noqa: BLE001
        batch, status, error = [], ("error" if src.verified else "unverified"), f"{type(e).__name__}: {str(e)[:200]}"
    return src, batch, status, error, round(time.monotonic() - t0, 1)


def run_sources(sources, prev_health, workers=8, deadline_s=None):
    """Run every source on a few background threads. A source that has not answered after
    deadline_s is skipped for today (its earlier postings are carried forward) instead of holding
    up the whole run. The threads are daemons, so a stuck one cannot block the program's exit."""
    deadline_s = SOURCE_DEADLINE_S if deadline_s is None else deadline_s
    prev = {h["name"]: h for h in prev_health or []}
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    raw, health = [], []
    n = len(sources)
    results = [None] * n
    todo, finished = queue.Queue(), queue.Queue()
    for i in range(n):
        todo.put(i)

    def worker():
        while True:
            try:
                i = todo.get_nowait()
            except queue.Empty:
                return
            try:
                finished.put((i, run_one(sources[i])))
            except Exception as e:                                   # noqa: BLE001
                finished.put((i, (sources[i], [], "error", str(e)[:300], 0.0)))

    for _ in range(max(1, min(workers, n))):
        threading.Thread(target=worker, daemon=True).start()
    t_end, done = time.monotonic() + deadline_s, 0
    while done < n and time.monotonic() < t_end:
        try:
            i, r = finished.get(timeout=max(0.05, min(5.0, t_end - time.monotonic())))
        except queue.Empty:
            continue
        results[i] = r
        done += 1
        print(f"  [{done:2d}/{n}] {r[2]:8s} {r[0].name} — {len(r[1])} found in {r[4]:.0f} s", flush=True)   # progress
    for i, r in enumerate(results):
        if r is None:
            results[i] = (sources[i], [], "error",
                          f"no answer within {deadline_s / 60:.0f} min — skipped today, earlier postings kept", float(deadline_s))
            print(f"  [ skip] timeout  {sources[i].name} — no answer after {deadline_s} s, skipped today", flush=True)
    for src, batch, status, error, secs in results:
        p = prev.get(src.name, {})
        ok = status in ("ok", "low")
        health.append({
            "name": src.name, "group": src.group, "type": src.kind, "status": status, "raw": len(batch),
            "kept": 0, "carried": 0, "error": error, "seconds": secs,
            "last_ok": now if ok else p.get("last_ok"),
            "bad_since": None if ok else (p.get("bad_since") or C.today().isoformat()),
            "previous": p.get("status"), "verified": src.verified, "verification": src.verification, "url": src.url,
            "note": src.cfg.get("note") or ""})
        raw.extend(batch)
    return raw, health


def carry_forward(health, prev_jobs):
    """A source that fails today keeps its still-open postings from the last deployed
    jobs.json, for at most CARRY_MAX_DAYS after its last good run."""
    t = C.today().isoformat()
    now = dt.datetime.now(dt.timezone.utc)
    out = []
    for h in health:
        if h["status"] not in BAD or not h.get("last_ok"):
            continue
        try:
            age = now - dt.datetime.fromisoformat(h["last_ok"])
        except (TypeError, ValueError):
            continue
        if age > dt.timedelta(days=CARRY_MAX_DAYS):
            continue
        kept = []
        for j in prev_jobs or []:
            if h["name"] in (j.get("sources") or []) and (j.get("deadline") or "9999") >= t:
                j = dict(j, carried=True, relevant=True, hints={}, description=j.get("summary", ""))
                kept.append(j)
        h["carried"] = len(kept)
        out.extend(kept)
    return out


# ---------------------------------------------------------------------------
# Normalise, de-duplicate, filter
# ---------------------------------------------------------------------------
def normalise(r):
    title = C.clean(r.get("title"))
    url = (r.get("url") or "").strip()
    if not title or not url.startswith(("http://", "https://")):
        return None
    org = C.clean(r.get("org"))
    return {"id": C.job_id(url, title, org), "title": title[:240], "org": org[:160],
            "location": C.clean(r.get("location"))[:160], "url": url, "apply": r.get("apply") or "",
            "source": r.get("source", ""), "sources": [r.get("source", "")], "posted": r.get("posted"),
            "deadline": r.get("deadline"), "description": (r.get("description") or "")[:8000],
            "fields_text": r.get("fields_text") or "", "hints": r.get("hints") or {},
            "pinned": bool(r.get("pinned")), "issue": r.get("issue") or ""}


def _richness(j):
    return (bool(j.get("pinned")), bool(j.get("deadline")), len(j.get("description") or ""), bool(j.get("org")))


def merge(a, b):
    keep, other = (a, b) if _richness(a) >= _richness(b) else (b, a)
    keep["sources"] = sorted(set(a.get("sources") or []) | set(b.get("sources") or []))
    for f in ("deadline", "org", "location", "posted", "apply", "issue"):
        if not keep.get(f) and other.get(f):
            keep[f] = other[f]
    if a.get("posted") and b.get("posted"):
        keep["posted"] = min(a["posted"], b["posted"])
    keep["pinned"] = bool(a.get("pinned") or b.get("pinned"))
    return keep


def dedupe_ids(jobs):
    by_id = {}
    for j in jobs:
        by_id[j["id"]] = merge(by_id[j["id"]], j) if j["id"] in by_id else j
    return list(by_id.values())


def dedupe_titles(jobs):
    """The same posting on two boards: same title and employer, or the same long title in
    the same country."""
    out, index = [], {}
    for j in jobs:
        t = C.fold(j["title"])[:90]
        keys = []
        if j.get("org"):
            keys.append(("org", t, C.fold(j["org"])[:40]))
        if len(t) >= 40 and j.get("country"):
            keys.append(("country", t, j["country"]))
        twin = next((index[k] for k in keys if k in index), None)
        if twin is None:
            out.append(j)
            for k in keys:
                index[k] = len(out) - 1
        else:
            out[twin] = merge(out[twin], j)
            for k in keys:
                index.setdefault(k, twin)
    return out


def keep(j):
    t = C.today()
    if j.get("deadline") and j["deadline"] < t.isoformat():
        return False
    if not j.get("relevant", True):
        return False
    if not j.get("pinned") and not j.get("deadline") and j.get("posted"):
        if j["posted"] < (t - dt.timedelta(days=MAX_AGE_DAYS)).isoformat():
            return False
    return True


# ---------------------------------------------------------------------------
# Enrichment: detail pages, CV match
# ---------------------------------------------------------------------------
def _load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def detail_text(url):
    r = C.get(url)
    if "html" not in (getattr(r, "headers", None) or {}).get("content-type", "html"):
        return ""
    soup = BeautifulSoup(r.text, "html.parser")
    for bad in soup(["nav", "header", "footer", "script", "style", "noscript", "form", "aside", "svg"]):
        bad.decompose()
    node = soup.find("main") or soup.find("article") or soup.find(attrs={"role": "main"}) or soup.body or soup
    return C.clean(node.get_text(" "))[:8000]


def enrich(jobs):
    """Postings with only a one-line summary (EURAXESS, link boards) are read in full when
    they rank well, so wet/dry, visa and deadline can be judged. Cached between runs."""
    if os.environ.get("LH_NO_ENRICH"):
        return {"status": "off", "detail": "LH_NO_ENRICH is set"}
    path = os.path.join(CACHE_DIR, "details.json")
    cache = _load_json(path, {})
    short = [j for j in jobs if len(j.get("description") or "") < 500 and not j.get("carried")
             and not j["url"].lower().endswith(".pdf") and "linkedin.com" not in j["url"]]
    picked = sorted(short, key=lambda j: -j.get("_s", 0))[:ENRICH_MAX]
    fetched = failed = used = 0
    t = C.today().isoformat()
    t_stop = time.monotonic() + ENRICH_BUDGET_S
    for j in picked:
        entry = cache.get(j["id"])
        if entry is None:
            if time.monotonic() > t_stop:                    # out of time today: try again tomorrow
                continue
            try:
                entry = {"text": C.call_with_deadline(45, detail_text, j["url"]), "on": t}
                fetched += 1
            except Exception:                                        # noqa: BLE001
                entry = {"text": "", "on": t}
                failed += 1
            cache[j["id"]] = entry
        if entry["text"] and len(entry["text"]) > len(j.get("description") or ""):
            j["description"] = entry["text"]
            K.classify(j)
            if not j.get("deadline"):
                j["deadline"] = C.deadline_from_text(entry["text"])
            used += 1
    cutoff = (C.today() - dt.timedelta(days=60)).isoformat()
    cache = {k: v for k, v in cache.items() if v.get("on", "") >= cutoff}
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f)
    return {"status": "ok", "detail": f"{fetched} pages read, {used} postings completed, {failed} failed"}


def cv_match(jobs):
    if not os.path.exists(CV_FILE):
        return {"status": "off", "detail": "no CV text"}
    with open(CV_FILE, encoding="utf-8") as f:
        cv = f.read()
    texts = [" ".join((j["title"], j["title"], j.get("description", "")[:3000], j.get("fields_text", ""))) for j in jobs]
    for j, sim in zip(jobs, cvmatch.similarity(cv, texts)):
        j["cv"] = sim
    return {"status": "ok", "detail": f"{len(jobs)} postings compared with scraper/{SITE.get("cv")}"}


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
def public(j):
    out = {k: j[k] for k in OUT_KEYS if j.get(k) not in (None, "", [], False, 0)}
    out["summary"] = C.truncate(j.get("summary") or j.get("description") or "", SUMMARY_CHARS)
    return out


def payload(jobs, health, default_id, profiles, classifiers, sample=False):
    return {
        "version": 1,
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "today": C.today().isoformat(),
        "sample": sample,
        "site": {"title": SITE["title"], "for": SITE["person"], "first_name": SITE["first_name"], "tagline": SITE["tagline"], "repo": C.REPO},
        "counts": {"jobs": len(jobs), "sources": len(health),
                   "sources_ok": sum(h["status"] in ("ok", "low") for h in health),
                   "by_region": dict(Counter(j["region"] for j in jobs))},
        "taxonomy": {"fields": T.FIELDS,
                     "subfields": {sid: {"label": lab, "field": T.field_of(sid)} for sid, (lab, _) in T.SUBFIELDS.items()}},
        "labels": {"kinds": K.KINDS, "sectors": K.SECTORS, "labs": K.LABS, "visa": K.VISA, "levels": K.LEVELS,
                   "regions": REGIONS, "countries": {cc: v[0] for cc, v in COUNTRIES.items()}},
        "profiles": {"default": default_id, "soft_cap": P.SOFT_CAP, "pin_floor": P.PIN_FLOOR,
                     "list": list(profiles.values())},
        "programmes": load_yaml("programmes.yaml").get("programmes", []),
        "classifiers": classifiers,
        "health": health,
        "jobs": [public(j) for j in jobs],
    }


def load_previous(path):
    data = _load_json(path, {})
    return {} if data.get("sample") else data


def notifications(jobs, health, default_id, notify_dir):
    os.makedirs(notify_dir, exist_ok=True)
    t = C.today().isoformat()
    new = sorted((j for j in jobs if j.get("first_seen") == t and j["scores"].get(default_id, 0) >= DIGEST_MIN),
                 key=lambda j: -j["scores"][default_id])
    lines = []
    if new:
        lines.append(f"### {len(new)} new position{'s' if len(new) != 1 else ''} for {SITE['first_name']} ({t})\n")
        for j in new[:15]:
            where = j.get("location") or COUNTRIES.get(j.get("country"), ("",))[0]
            dl = f" — closes {j['deadline']}" if j.get("deadline") else ""
            title = j["title"].replace("[", "(").replace("]", ")")
            lines.append(f"- **{j['scores'][default_id]}** [{title}]({j['url']}) · {j.get('org', '')} · {where}{dl}")
        if len(new) > 15:
            lines.append(f"\n…and {len(new) - 15} more on the site.")
    broken = [h for h in health if h["status"] in ("error", "robots", "empty") and h.get("verified")
              and h.get("previous") not in BAD]
    if broken:
        lines.append("\n### Sources that stopped working today\n")
        lines += [f"- {h['name']}: {h['status']} — {h.get('error') or 'returned nothing'}" for h in broken]
    with open(os.path.join(notify_dir, "digest.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description="Collect, classify and rank positions for Latent Space.")
    ap.add_argument("--only", help="run only sources whose name contains this text")
    ap.add_argument("--offline", action="store_true", help="read tests/fixtures instead of the internet")
    ap.add_argument("--out", default=OUT, help="where to write jobs.json (default docs/jobs.json)")
    ap.add_argument("--notify", default=NOTIFY, help="where to write the digest (default notify/)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--no-llm", action="store_true", help="skip the Claude fit check")
    a = ap.parse_args(argv)
    if a.offline:
        import offline
        offline.install()
        os.environ.setdefault("LH_NO_ENRICH", "1")
    t_start = time.monotonic()
    prev = load_previous(a.out)
    default_id, profiles = P.load()
    sources = build_sources()
    if a.only:
        sources = [s for s in sources if a.only.lower() in s.name.lower()]
    print(f"Latent Space — {len(sources)} sources, today {C.today()}")

    raw, health = run_sources(sources, prev.get("health"), a.workers)
    jobs = dedupe_ids([j for j in map(normalise, raw) if j])
    for j in jobs:
        K.classify(j)
    have = {j["id"] for j in jobs}
    jobs += [j for j in carry_forward(health, prev.get("jobs")) if j["id"] not in have]
    jobs = dedupe_titles([j for j in jobs if keep(j)])

    prof = profiles[default_id]
    for j in jobs:
        j["_s"] = P.score(j, prof)[0]
    enrich_status = enrich(jobs)
    jobs = [j for j in jobs if keep(j)]
    cv_status = cv_match(jobs)
    for j in jobs:
        j["_s"] = P.score(j, prof)[0]
    if a.no_llm:
        llm_status = {"status": "off", "detail": "--no-llm"}
    else:
        candidates = sorted((j for j in jobs if j["_s"] >= 45 and not j.get("carried")), key=lambda j: -j["_s"])
        llm_status = llm_fit.label_jobs(candidates, jobs)

    first = {j["id"]: j.get("first_seen") for j in prev.get("jobs") or []}
    t = C.today().isoformat()
    for j in jobs:
        j["first_seen"] = first.get(j["id"]) or t
        j["scores"] = {pid: P.score(j, p)[0] for pid, p in profiles.items()}
    if len(jobs) > MAX_JOBS:
        jobs = sorted(jobs, key=lambda j: -max(j["scores"].values()))[:MAX_JOBS]
    jobs.sort(key=lambda j: (-j["scores"][default_id], j.get("deadline") or "9999", j["title"]))

    kept = Counter(s for j in jobs for s in j["sources"])
    for h in health:
        h["kept"] = kept.get(h["name"], 0)
    classifiers = {"enrich": enrich_status, "cv": cv_status, "llm": llm_status,
                   "robots_blocked": len(C.ROBOTS_BLOCKED)}
    data = payload(jobs, health, default_id, profiles, classifiers, sample=a.offline)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"), default=str)
    notifications(jobs, health, default_id, a.notify)

    ok = sum(h["status"] in ("ok", "low") for h in health)
    print(f"\n{len(jobs)} positions from {ok}/{len(health)} healthy sources -> {a.out} "
          f"({time.monotonic() - t_start:.0f} s)")
    for h in health:
        if h["status"] != "ok":
            print(f"  {h['status']:10s} {h['name']}: {h.get('error') or str(h['raw']) + ' found'}")
    print("Classifiers:", json.dumps(classifiers))
    return 0


if __name__ == "__main__":
    sys.exit(main())
