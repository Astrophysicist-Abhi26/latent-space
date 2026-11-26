"""
Shared helpers for every Latent Space source.

One polite HTTP session (retries, robots.txt, one request per host per second),
a date reader that understands the formats job boards and Indian institute pages
actually use, and small text helpers. Modelled on Event Horizon 2.0's common.py.
"""

import datetime as dt
import hashlib
import html as _html
import os
import re
import threading
import time
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests
from dateutil import parser as dateparser
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

REPO = os.environ.get("GITHUB_REPOSITORY", "Astrophysicist-Abhi26/latent-space")
UA = f"Latent Space/1.0 (research-job aggregator; +https://github.com/{REPO})"
ROBOTS_TOKEN = "Latent Space"
TIMEOUT = 30
CONNECT_TIMEOUT = 10
HOST_GAP = float(os.environ.get("LH_HOST_GAP", "1.0"))   # seconds between two requests to one host

BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
_BROWSER_HEADERS = {"User-Agent": BROWSER_UA,
                    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-GB,en;q=0.9"}


RETRY_AFTER_CAP = 20   # seconds; a site that says "come back in an hour" is not waited for


class CappedRetry(Retry):
    """urllib3's Retry obeys a server's Retry-After header for as long as it asks. Here the
    wait is capped, so a busy site is reported as failing instead of stalling the whole run."""
    def get_retry_after(self, response):
        v = super().get_retry_after(response)
        return None if v is None else min(v, RETRY_AFTER_CAP)


def call_with_deadline(seconds, fn, *args, **kw):
    """Run fn on a background thread and give up after `seconds` (TimeoutError). requests'
    timeouts only cover silences, so a server that trickles bytes could otherwise last for ever."""
    box = {}

    def run():
        try:
            box["v"] = fn(*args, **kw)
        except BaseException as e:                                  # noqa: BLE001
            box["e"] = e
    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(seconds)
    if t.is_alive():
        raise TimeoutError(f"no answer within {seconds:.0f} s")
    if "e" in box:
        raise box["e"]
    return box.get("v")


def session():
    s = requests.Session()
    retry = CappedRetry(total=3, connect=1, backoff_factor=1.5,
                  status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=("GET", "POST"), respect_retry_after_header=True)
    adapter = HTTPAdapter(max_retries=retry, pool_maxsize=16)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update({"User-Agent": UA})
    return s


HTTP = session()


# ---------------------------------------------------------------------------
# robots.txt, dead hosts and pacing
# ---------------------------------------------------------------------------
# robots.txt is a site's published rule book for automated readers (RFC 9309).
# Web pages are only read when it allows them. Feeds and documented job-board
# APIs (RSS, Greenhouse, Lever, Ashby, Workable) are published for programs to
# read, so they are fetched with feed=True and robots.txt is not consulted.
# LH_ROBOTS = enforce (default) | report (read anyway, list what would be skipped) | off
class RobotsDisallowed(requests.exceptions.RequestException):
    """The site's robots.txt asks automated tools not to read this page."""


_ROBOTS = {}
_ROBOTS_LOCK = threading.Lock()
ROBOTS_BLOCKED = []
_DEAD_HOSTS = set()
_LAST_HIT = {}
_HOST_LOCKS = {}
_LOCKS_LOCK = threading.Lock()


def robots_mode():
    return os.environ.get("LH_ROBOTS", "enforce").lower()


def robots_allowed(url):
    from urllib import robotparser
    p = urlparse(url)
    root = f"{p.scheme}://{p.netloc}"
    with _ROBOTS_LOCK:
        rp = _ROBOTS.get(root)
    if rp is None:
        rp = robotparser.RobotFileParser()
        try:
            r = HTTP.get(root + "/robots.txt", timeout=(CONNECT_TIMEOUT, 15))
            text = r.text if r.status_code < 400 else ""
            if "html" in (getattr(r, "headers", None) or {}).get("content-type", "").lower():
                text = ""                       # a "page not found" page served as robots.txt
            rp.parse(text.splitlines())
        except requests.exceptions.ConnectTimeout:
            _DEAD_HOSTS.add(p.netloc.lower())
            rp.parse([])
        except Exception:
            rp.parse([])
        with _ROBOTS_LOCK:
            _ROBOTS[root] = rp
    return rp.can_fetch(ROBOTS_TOKEN, url)


def check_robots(url):
    mode = robots_mode()
    if mode == "off" or robots_allowed(url):
        return
    ROBOTS_BLOCKED.append(url)
    if mode == "enforce":
        raise RobotsDisallowed(f"the site's robots.txt asks automated tools not to read {url}")


def reset():
    """Forget robots files, dead hosts and pacing (tests, doctor)."""
    with _ROBOTS_LOCK:
        _ROBOTS.clear()
    ROBOTS_BLOCKED.clear()
    _DEAD_HOSTS.clear()
    _LAST_HIT.clear()


def _pace(host):
    if HOST_GAP <= 0:
        return
    with _LOCKS_LOCK:
        lock = _HOST_LOCKS.setdefault(host, threading.Lock())
    with lock:
        wait = _LAST_HIT.get(host, 0.0) + HOST_GAP - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _LAST_HIT[host] = time.monotonic()


def _timeout(kw):
    t = kw.pop("timeout", TIMEOUT)
    return (min(CONNECT_TIMEOUT, t), t) if isinstance(t, (int, float)) else t


def _finish(r):
    r.raise_for_status()
    # A server that names no charset gets ISO-8859-1 from requests, which turns UTF-8
    # into mojibake ("Itâs"). Let the bytes decide instead.
    ctype = (getattr(r, "headers", None) or {}).get("content-type", "")
    if "charset" not in ctype.lower() and any(t in ctype for t in ("text", "html", "xml")):
        r.encoding = r.apparent_encoding or "utf-8"
    return r


def get(url, feed=False, insecure_ok=False, headers=None, **kw):
    """GET with retries, robots.txt, per-host pacing and two fallbacks Indian institute
    sites need: a browser User-Agent after 403/406, and (only for sources marked
    insecure_ok) reading a page whose server ships an incomplete TLS chain."""
    timeout = _timeout(kw)
    headers = dict(headers or {})
    host = urlparse(url).netloc.lower()
    if host in _DEAD_HOSTS:
        raise requests.exceptions.ConnectTimeout(f"{host} did not answer earlier in this run")
    if not feed:
        check_robots(url)
    _pace(host)
    verify = True
    try:
        r = HTTP.get(url, headers=headers, timeout=timeout, **kw)
    except requests.exceptions.ConnectTimeout:
        _DEAD_HOSTS.add(host)
        raise
    except requests.exceptions.SSLError:
        if not insecure_ok:
            raise
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        verify = False
        r = HTTP.get(url, headers=headers, timeout=timeout, verify=False, **kw)
    if r.status_code in (403, 406):
        _pace(host)
        r = HTTP.get(url, headers={**headers, **_BROWSER_HEADERS}, timeout=timeout, verify=verify, **kw)
    return _finish(r)


def post_json(url, payload, feed=False, headers=None, **kw):
    timeout = _timeout(kw)
    host = urlparse(url).netloc.lower()
    if host in _DEAD_HOSTS:
        raise requests.exceptions.ConnectTimeout(f"{host} did not answer earlier in this run")
    if not feed:
        check_robots(url)
    _pace(host)
    h = {"Accept": "application/json", "Content-Type": "application/json", **(headers or {})}
    r = HTTP.post(url, json=payload, headers=h, timeout=timeout, **kw)
    return _finish(r)


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------
def clean(text):
    if text is None:
        return ""
    text = _html.unescape(str(text)).replace("\u00a0", " ").replace("\u200b", "")
    return re.sub(r"\s+", " ", text).strip()


def html_text(markup):
    """Visible text of an HTML fragment, one space between blocks."""
    if not markup:
        return ""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(_html.unescape(markup) if "&lt;" in markup else markup, "html.parser")
    for bad in soup(["script", "style", "noscript"]):
        bad.decompose()
    return clean(soup.get_text(" "))


def truncate(text, n):
    text = clean(text)
    if len(text) <= n:
        return text
    cut = text[:n].rsplit(" ", 1)[0].rstrip(",;:-–")
    return cut + "…"


def fold(text):
    """Lower-case ASCII skeleton for comparisons ("Münster" -> "munster")."""
    t = unicodedata.normalize("NFKD", clean(text)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


_TRACKING = re.compile(r"^(utm_\w+|gh_src|gh_jid|source|src|ref|lever-source|lever-origin|"
                       r"trk|trackingid|refid|mc_cid|mc_eid|fbclid|gclid)$", re.I)


def canonical_url(url):
    if not url:
        return ""
    p = urlparse(url.strip())
    query = urlencode([(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                       if not _TRACKING.match(k)])
    path = re.sub(r"/+$", "", p.path) or "/"
    return urlunparse(((p.scheme or "https").lower(), p.netloc.lower().removeprefix("www."),
                       path, "", query, ""))


def job_id(url, title="", org=""):
    key = canonical_url(url) or (fold(title) + "|" + fold(org))
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def text_hash(*parts):
    return hashlib.sha1("\n".join(p or "" for p in parts).encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------
def today():
    """Today's date; LH_TODAY=YYYY-MM-DD pins it (tests, reproducible runs)."""
    pinned = os.environ.get("LH_TODAY")
    return dt.date.fromisoformat(pinned) if pinned else dt.date.today()


_MON = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_MONTH = (r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
          r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?")
_DATE_RES = [
    ("ymd", re.compile(r"\b(20\d\d)-(\d{1,2})-(\d{1,2})(?!\d)")),     # also "2026-11-05T10:00:00"
    ("dmy_num", re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](20\d\d)\b")),
    ("dmy_txt", re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s*(?:of\s+)?" + _MONTH + r",?\s+(20\d\d)\b", re.I)),
    ("mdy_txt", re.compile(r"\b" + _MONTH + r"\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(20\d\d)\b", re.I)),
]


def _mk(y, m, d):
    try:
        return dt.date(int(y), int(m), int(d))
    except ValueError:
        return None


def find_dates(text, dayfirst=True):
    """All dates in `text`, as (position, date), in reading order."""
    out = []
    for kind, rx in _DATE_RES:
        for m in rx.finditer(text or ""):
            g = m.groups()
            if kind == "ymd":
                d = _mk(g[0], g[1], g[2])
            elif kind == "dmy_num":
                a, b, y = int(g[0]), int(g[1]), g[2]
                d = _mk(y, b, a) if (dayfirst or b > 12) and a <= 31 else _mk(y, a, b)
                if d is None:
                    d = _mk(y, a, b)
            elif kind == "dmy_txt":
                d = _mk(g[2], _MON[g[1].lower()[:3]], g[0])
            else:
                d = _mk(g[2], _MON[g[0].lower()[:3]], g[1])
            if d:
                out.append((m.start(), d))
    out.sort(key=lambda x: x[0])
    # the same date found by two patterns at overlapping positions counts once
    dedup, last = [], None
    for pos, d in out:
        if last and abs(pos - last[0]) < 4 and d == last[1]:
            continue
        dedup.append((pos, d))
        last = (pos, d)
    return dedup


def parse_date(value, dayfirst=True):
    """ISO date string from a date-like value (str, struct_time, epoch ms, datetime)."""
    if value in (None, ""):
        return None
    if isinstance(value, dt.datetime):
        return value.date().isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, time.struct_time):
        return dt.date(value.tm_year, value.tm_mon, value.tm_mday).isoformat()
    if isinstance(value, (int, float)):
        secs = value / 1000 if value > 1e11 else value
        return dt.datetime.fromtimestamp(secs, dt.timezone.utc).date().isoformat()
    s = clean(value)
    found = find_dates(s, dayfirst)
    if found:
        return found[0][1].isoformat()
    if len(s) <= 40:
        try:   # an ISO-like "2026-11-05..." is always year-month-day, whatever the source's habit
            return dateparser.parse(s, dayfirst=dayfirst and not re.match(r"\d{4}-", s), fuzzy=True).date().isoformat()
        except (ValueError, OverflowError, TypeError):
            return None
    return None


DEADLINE_CUE = re.compile(
    r"(application deadline|closing date|clos(?:es|ing)(?: on)?|deadline(?: for applications?)?|"
    r"last date(?: (?:of|for) (?:receipt|submission|application)s?)?|apply (?:by|before|until|no later than)|"
    r"applications? (?:will be )?(?:accepted|received|considered) (?:until|till|by|before)|"
    r"due (?:by|date)|bewerbungsfrist|date limite|walk-?in(?:[- ]interview)?(?: (?:on|date))?|"
    r"expires?(?: on)?|valid (?:until|through))", re.I)


def deadline_from_text(text, dayfirst=True, horizon_days=550):
    """The date that follows a deadline cue ("Last date: 15.12.2026"), if it is not in
    the past and not absurdly far away."""
    text = text or ""
    t0 = today()
    for cue in DEADLINE_CUE.finditer(text):
        window = text[cue.end(): cue.end() + 90]
        for _, d in find_dates(window, dayfirst):
            if t0 - dt.timedelta(days=1) <= d <= t0 + dt.timedelta(days=horizon_days):
                return d.isoformat()
            break
    return None


def days_until(iso_date):
    if not iso_date:
        return None
    return (dt.date.fromisoformat(iso_date) - today()).days
