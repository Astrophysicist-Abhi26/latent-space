"""
RSS / Atom sources (sources.yaml entries with `type: rss`).

Feeds are published for programs to read, so robots.txt is not consulted for them.
A source may list several URLs, and a URL containing {q} is fetched once per entry
of `queries`. Each `parser` knows where one family of boards puts the employer,
location and closing date:

  madgex     Nature Careers, Science Careers, Times Higher Education, Chronicle,
             Inside Higher Ed (all run on Madgex: "salary:", "employer:", ..., location)
  mpg        Max Planck Society job feed
  jobrxiv    jobRxiv (WP Job Manager feed)
  labelled   feeds whose description says "Location: ...", "Closing date: ..." (jobs.ac.uk)
  wordpress  WordPress category feeds (Biotecnika)
  generic    anything else
"""

import re
from urllib.parse import quote_plus

import feedparser
from bs4 import BeautifulSoup

import common as C


def posting(title, url, source, org="", location="", description="", posted=None, deadline=None,
            apply_url="", hints=None, **extra):
    """The raw record every source returns."""
    return {"title": C.clean(title), "url": (url or "").strip(), "source": source, "org": C.clean(org),
            "location": C.clean(location), "description": C.clean(description), "posted": posted,
            "deadline": deadline, "apply": apply_url or "", "hints": dict(hints or {}), **extra}


def hints_of(src):
    keys = ("kind", "sector", "country", "lab", "topics", "keep_untagged")
    return {k: src[k] for k in keys if src.get(k) is not None}


def expand_urls(src):
    out = []
    for u in src.get("urls") or [src["url"]]:
        if "{q}" in u:
            out.extend(u.replace("{q}", quote_plus(q)) for q in src.get("queries") or [])
        else:
            out.append(u)
    return out


def _lines(markup):
    soup = BeautifulSoup(markup or "", "html.parser")
    return [C.clean(x) for x in soup.get_text("\n").split("\n") if C.clean(x)]


def _summary_html(e):
    if e.get("content"):
        return " ".join(c.get("value", "") for c in e["content"])
    return e.get("summary") or e.get("description") or ""


_SALARY = re.compile(r"\d|competitive|negotiable|salary|stipend|£|€|\$|\bgrade\b|not specified|commensurate|\bTVöD\b|\bTV-?L\b", re.I)


def parse_madgex(e):
    """Madgex descriptions read: "<salary>:", "<employer>:", <details ...>, <location>."""
    lines = _lines(_summary_html(e))
    org = loc = ""
    if lines and lines[0].endswith(":") and _SALARY.search(lines[0]):
        lines = lines[1:]
    if lines and lines[0].endswith(":"):
        org = lines[0].rstrip(":").strip()
        lines = lines[1:]
    if len(lines) >= 2 and len(lines[-1]) <= 80:
        loc = lines[-1]
        lines = lines[:-1]
    return org, loc, " ".join(lines)


_MPI = re.compile(r"(Max Planck (?:Institute|Research Unit|Center|Centre)[\w\s,&\-]*?)(?=[.;:()]|\s+(?:in|at|is|offers|invites|seeks)\b|$)", re.I)


def parse_mpg(e):
    text = C.html_text(_summary_html(e))
    m = _MPI.search(e.get("title", "") + " " + text)
    org = C.clean(m.group(1)) if m else "Max Planck Society"
    return org, "", text


def parse_jobrxiv(e):
    org = e.get("job_listing_company") or e.get("job_listing_company_name") or e.get("author") or ""
    loc = e.get("job_listing_location") or ""
    return org, loc, C.html_text(_summary_html(e))


_LABEL = {"org": r"(?:employer|institution|organi[sz]ation|company|university)",
          "location": r"(?:location|place of work|based in|campus)"}


_NEXT_LABEL = (r"(?=\s+(?:employer|institution|organi[sz]ation|company|location|place of work|salary|closing date|"
               r"closes|hours|contract( type)?|placed on|reference|expires|department|faculty|grade)\s*:|$)")


def _labelled(text, label):
    m = re.search(label + r"\s*:\s*(.+?)" + _NEXT_LABEL, text, re.I)
    return C.clean(m.group(1))[:120] if m else ""


def parse_labelled(e):
    text = C.html_text(_summary_html(e))
    return _labelled(text, _LABEL["org"]), _labelled(text, _LABEL["location"]), text


_RECRUIT = re.compile(r"^(.{3,80}?)\s+(?:Recruitment|Jobs?|Vacanc\w+|Hiring|Opening|Walk-?in)\b", re.I)


def parse_wordpress(e):
    text = C.html_text(_summary_html(e))
    m = _RECRUIT.match(e.get("title", ""))
    return (C.clean(m.group(1)) if m else ""), "", text


def parse_generic(e):
    text = C.html_text(_summary_html(e))
    return C.clean(e.get("author", "")), C.clean(e.get("location", "")), text


PARSERS = {"madgex": parse_madgex, "mpg": parse_mpg, "jobrxiv": parse_jobrxiv, "labelled": parse_labelled,
           "wordpress": parse_wordpress, "generic": parse_generic}


def fetch_rss(src):
    parse = PARSERS[src.get("parser", "generic")]
    dayfirst = src.get("dayfirst", True)
    include = re.compile(src["include"], re.I) if src.get("include") else None
    exclude = re.compile(src["exclude"], re.I) if src.get("exclude") else None
    out, seen = [], set()
    urls = expand_urls(src)
    errors = []
    for url in urls:
        try:
            r = C.get(url, feed=True)
            feed = feedparser.parse(r.content)
            if feed.bozo and not feed.entries:
                raise ValueError(f"{url} is not a readable feed ({feed.get('bozo_exception')})")
        except Exception as e:                       # noqa: BLE001 — one bad URL must not sink the source
            errors.append(e)
            continue
        for e in feed.entries[: src.get("max_items", 200)]:
            link = e.get("link") or ""
            title = C.clean(e.get("title", ""))
            if not link or not title or link in seen:
                continue
            if include and not include.search(title):
                continue
            if exclude and exclude.search(title):
                continue
            seen.add(link)
            org, loc, text = parse(e)
            posted = C.parse_date(e.get("published_parsed") or e.get("updated_parsed") or e.get("published"))
            out.append(posting(
                title, link, src["name"], org=org or src.get("org", ""), location=loc or src.get("location", ""),
                description=text, posted=posted, deadline=C.deadline_from_text(text, dayfirst),
                hints=hints_of(src)))
    if errors and len(errors) == len(urls):
        raise errors[0]
    return out


# ── Hacker News: the monthly "Ask HN: Who is hiring?" thread ─────────────────
HN_SEARCH = "https://hn.algolia.com/api/v1/search_by_date?tags=story,author_whoishiring&hitsPerPage=5"
HN_ITEM = "https://hn.algolia.com/api/v1/items/{id}"
_HN_ROLE = re.compile(r"engineer|scientist|intern|research|\bML\b|machine learning|\bAI\b|data|developer|analyst|quant", re.I)
_HN_PLACE = re.compile(r"remote|on-?site|hybrid|india|bengaluru|bangalore|pune|london|berlin|paris|zurich|amsterdam|"
                       r"san francisco|\bsf\b|new york|\bnyc\b|boston|seattle|toronto|singapore|tokyo|\b[A-Z][a-z]+,\s?[A-Z]{2}\b", re.I)


def fetch_hn_hiring(src):
    """One posting per top-level comment of the latest 'Who is hiring?' thread (HN's Algolia API).
    Comments start 'Company | Role | Place | ...'; only machine-learning roles survive classification."""
    import json as _json
    hits = _json.loads(C.get(HN_SEARCH).text).get("hits", [])
    story = next((h for h in hits if "who is hiring" in (h.get("title") or "").lower()), None)
    if not story:
        return []
    item = _json.loads(C.get(HN_ITEM.format(id=story["objectID"])).text)
    out = []
    for c in (item.get("children") or [])[: int(src.get("max_items", 700))]:
        lines = _lines(c.get("text") or "")
        if not lines:
            continue
        head = lines[0][:300]
        parts = [p.strip() for p in head.split("|") if p.strip()]
        if len(parts) < 2:
            continue
        org = parts[0][:80]
        role = next((p for p in parts[1:] if _HN_ROLE.search(p)), parts[1])[:140]
        place = next((p for p in parts[1:] if _HN_PLACE.search(p) and p != role), "")[:120]
        out.append(posting(role, f"https://news.ycombinator.com/item?id={c.get('id')}", src["name"], org=org, location=place,
                           description=" ".join(lines)[:3000], posted=(c.get("created_at") or "")[:10] or None,
                           hints=hints_of(src)))
    return out
