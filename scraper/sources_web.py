"""
Web-page sources: EURAXESS search results, boards that list job links (Academic
Positions, IndiaBioscience, EuroScienceJobs, SciLifeLab ...) and institute pages
(NCBS, IISc, THSTI ...) read by a generic extractor. robots.txt is honoured for all.

Every parser anchors on what is most stable on the page (the job link pattern, or a
link and a date in the same small block) and reads the rest from the block's text,
so a redesign of the page's CSS does not break it.
"""

import re
import time
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

import common as C
from geo import country_name, locate
from sources_feeds import hints_of, posting

_CHROME = ("nav", "header", "footer", "script", "style", "noscript", "form", "aside", "svg")


def _soup(url, src):
    r = C.get(url, insecure_ok=bool(src.get("insecure_ok")))
    return BeautifulSoup(r.text, "html.parser")


def _text(node):
    return C.clean(node.get_text(" ")) if node is not None else ""


def _card(a, link_rx, base="", max_up=8, max_chars=2500):
    """The smallest ancestor of `a` that holds this job's details but no other job link
    (links compared as absolute URLs, so relative and absolute links both count)."""
    node, best = a, a.parent
    for _ in range(max_up):
        node = node.parent
        if node is None or node.name in ("body", "html", "[document]"):
            break
        hrefs = (urljoin(base, x["href"]).split("#")[0] for x in node.find_all("a", href=True))
        links = {h for h in hrefs if link_rx.search(h)}
        if len(links) > 1 or len(_text(node)) > max_chars:
            break
        best = node
    return best


# ---------------------------------------------------------------------------
# EURAXESS
# ---------------------------------------------------------------------------
_EU_JOB = re.compile(r"(?:^|euraxess\.ec\.europa\.eu)/jobs/(\d+)/?$")
_EU_LABELS = r"(?=\s+(?:Department|Work Locations|Research Field|Researcher Profile|Funding Programme|Application Deadline|Posted on)\b|$)"


def _eu_field(text, label):
    m = re.search(label + r":\s*(.+?)" + _EU_LABELS, text)
    return C.clean(m.group(1)) if m else ""


def parse_euraxess_card(card, a, src, base="https://euraxess.ec.europa.eu"):
    text = _text(card)
    title = _text(a)
    posted = C.parse_date((re.search(r"Posted on:?\s*(\d{1,2}\s+\w+\s+\d{4})", text) or [None, None])[1])
    deadline = C.parse_date((re.search(r"Application Deadline:?\s*(\d{1,2}\s+\w+\s+\d{4})", text) or [None, None])[1])
    m = re.search(r"Work Locations:\s*(.+?)" + _EU_LABELS, text)
    work = re.sub(r"^Number of offers:\s*\d+\s*,\s*", "", C.clean(m.group(1)) if m else "")
    parts = [p.strip() for p in work.split(",") if p.strip()]
    country, org = (parts + ["", ""])[:2]
    city = ", ".join(parts[2:])
    publisher = ""
    for x in card.find_all("a", href=True):
        if "/partnering/organisations/profile/" in x["href"]:
            publisher = _text(x)
            break
    fields = _eu_field(text, "Research Field")
    profile = _eu_field(text, "Researcher Profile")
    dept = _eu_field(text, "Department")
    after = text.split(title, 1)[1] if title in text else text
    summary = re.split(r"\s+(?:Department|Work Locations):", after, 1)[0]
    hints = hints_of(src)
    if "R2" in profile and "kind" not in hints:
        hints["kind"] = "postdoc"
    return posting(
        title, urljoin(base, a["href"]), src["name"], org=org or publisher, location=", ".join(x for x in (city, country) if x),
        description=" ".join(x for x in (summary, dept) if x), posted=posted, deadline=deadline, hints=hints,
        fields_text=fields, profile_text=profile)


# EURAXESS can be slow, or ask automated readers to wait. One EURAXESS source stops paging after
# this many seconds and keeps what it has, so a slow day cannot hold up the whole run.
EURAXESS_BUDGET_S = 480


def fetch_euraxess(src):
    out, seen, errors = [], set(), []
    t0, budget = time.monotonic(), float(src.get("budget_s", EURAXESS_BUDGET_S))
    for base in src["urls"]:
        if time.monotonic() - t0 > budget:
            break
        for page in range(int(src.get("max_pages", 20))):
            if page and time.monotonic() - t0 > budget:
                break
            url = base if page == 0 else base + ("&" if "?" in base else "?") + f"page={page}"
            try:
                soup = _soup(url, src)
            except Exception as e:                   # noqa: BLE001
                if page == 0:
                    errors.append(e)
                break
            new = 0
            for a in soup.find_all("a", href=True):
                m = _EU_JOB.search(a["href"].split("?")[0])
                if not m or m.group(1) in seen or not _text(a):
                    continue
                seen.add(m.group(1))
                card = _card(a, _EU_JOB, url)
                job = parse_euraxess_card(card, a, src)
                profile = job.get("profile_text", "")
                # First-stage-only offers (R1) are PhD positions: exactly what Kartik is after
                if profile and "R1" in profile and not re.search(r"R2|R3|R4", profile):
                    job.setdefault("hints", {})["kind"] = "phd"
                out.append(job)
                new += 1
            if not new:
                break
    if errors and len(errors) == len(src["urls"]):
        raise errors[0]
    return out


# ---------------------------------------------------------------------------
# Boards that list links to job pages
# ---------------------------------------------------------------------------
def _slug_name(slug):
    """'ncbs' -> 'NCBS', 'aix-marseille-universite' -> 'Aix Marseille Universite'"""
    words = re.sub(r"[-_]+", " ", slug).split()
    if len(words) == 1 and len(words[0]) <= 5:
        return words[0].upper()
    small = {"of", "for", "and", "the", "de", "der", "di", "du", "la", "le", "und", "van", "von"}
    return " ".join(w if (i and w in small) else w.capitalize() for i, w in enumerate(words))


_POSTED = re.compile(r"(?:posted|published|placed)(?: on)?:?\s*(.{6,30})", re.I)


def fetch_links(src):
    link_rx = re.compile(src["href"])
    org_rx = re.compile(src["org_from_href"]) if src.get("org_from_href") else None
    dayfirst = src.get("dayfirst", True)
    out, seen, errors = [], set(), []
    urls = src.get("urls") or [src["url"]]
    for url in urls:
        try:
            soup = _soup(url, src)
        except Exception as e:                       # noqa: BLE001
            errors.append(e)
            continue
        for bad in soup(_CHROME):
            bad.decompose()
        for a in soup.find_all("a", href=True):
            href = urljoin(url, a["href"]).split("#")[0]
            if not link_rx.search(href) or href in seen:
                continue
            title = _text(a)
            heading = a.find(["h1", "h2", "h3", "h4", "h5"])
            if heading is not None:
                title = _text(heading)
            if len(title) < 8 or re.fullmatch(r"(apply|view|details|read more|more|show more|see more)\W*", title, re.I):
                continue
            seen.add(href)
            card = _card(a, link_rx, url)
            text = _text(card)
            org = src.get("org", "")
            if org_rx and not org:
                m = org_rx.search(href)
                org = _slug_name(m.group(1)) if m else ""
            where = locate(text.replace(title, " "))
            posted = None
            m = _POSTED.search(text)
            if m:
                posted = C.parse_date(m.group(1), dayfirst)
            out.append(posting(
                title, href, src["name"], org=org, location=country_name(where["country"]) if where["country"] else "",
                description=text.replace(title, " ", 1), posted=posted,
                deadline=C.deadline_from_text(text, dayfirst), hints=hints_of(src)))
    if errors and len(errors) == len(urls):
        raise errors[0]
    return out



# ---------------------------------------------------------------------------
# Institute pages: a link and a date in the same small block
# ---------------------------------------------------------------------------
JOB_WORDS = re.compile(
    r"post-?doc|postdoctoral|research (associate|fellow|scientist|assistant)|project (scientist|associate|assistant|"
    r"coordinator|manager)|scientist|fellowship|\bJRF\b|\bSRF\b|technical (officer|assistant)|technician|"
    r"recruitment|vacanc|advertisement|\badvt\b|walk-?in|positions?\b|faculty|lab manager", re.I)
GENERIC_LINK = re.compile(r"^(click here|here|view|view details?|details|download( detail| details| advertisement| pdf)?|"
                          r"apply( now| online)?|advertisement|more|read more|pdf|notification|link|website)\W*$", re.I)
_CUT = re.compile(r"\s+(?:last date|closing date|deadline|date of interview|walk-?in|download|apply|view|click here|"
                  r"status of recruitment|open|closed)\b.*$", re.I)
_REF = re.compile(r"\b(?:[A-Z]{2,}[-/][A-Z0-9/-]{3,})\b")


def _block(a, max_chars=1200):
    node = a
    for _ in range(6):
        parent = node.parent
        if parent is None or parent.name in ("body", "html", "[document]", "table", "tbody", "ul", "ol"):
            break
        node = parent
        if node.name in ("tr", "li", "article"):
            break
        if node.name in ("p", "div", "section", "dd") and len(_text(node)) >= 40:
            break
    return node if len(_text(node)) <= max_chars else a.parent


def _row_title(row, link_text, cells_wanted=1):
    cells = [_text(c) for c in row.find_all(["td", "th"], recursive=False)] or [_text(c) for c in row.find_all(["td", "th"])]
    picked = []
    for c in cells:
        if not c or GENERIC_LINK.match(c) or C.find_dates(c) and len(c) < 25 or c == link_text:
            continue
        if re.fullmatch(r"[\d\s./-]+|open|closed|unreserved|not available", c, re.I):
            continue
        picked.append(c)
        if len(picked) == cells_wanted:
            break
    return " — ".join(picked)


def extract_listing(soup, url, src):
    for bad in soup(_CHROME):
        bad.decompose()
    href_rx = re.compile(src["href_filter"]) if src.get("href_filter") else None
    include = re.compile(src["include"], re.I) if src.get("include") else None
    exclude = re.compile(src["exclude"], re.I) if src.get("exclude") else None
    skip_if = re.compile(src["skip_if"], re.I) if src.get("skip_if") else None
    dayfirst = src.get("dayfirst", True)
    page_host = urlparse(url).netloc
    out, seen, seen_blocks = [], set(), set()
    for a in soup.find_all("a", href=True):
        raw = a["href"].strip()
        if raw.startswith(("mailto:", "javascript:", "tel:", "#")):
            continue
        href = urljoin(url, raw).split("#")[0]
        if href in seen or href.rstrip("/") == url.rstrip("/"):
            continue
        if href_rx and not href_rx.search(href):
            continue
        block = _block(a)
        if id(block) in seen_blocks:
            continue
        text = _text(block)
        if skip_if and skip_if.search(text):
            continue
        link_text = _text(a)
        if block.name == "tr":
            title = _row_title(block, link_text, int(src.get("title_cells", 1)))
        elif GENERIC_LINK.match(link_text) or len(link_text) < 8:
            title = text.replace(link_text, " ")
        else:
            title = link_text
        title = C.clean(_REF.sub(" ", _CUT.sub("", title)))
        title = re.sub(r"^(?:advt\.?|advertisement)\s*(?:no\.?)?\s*[\w./-]*\s*[:\-–]\s*", "", title, flags=re.I)
        title = re.sub(r"^(?:appointment|recruitment|engagement)\s+(?:of|for)\s+(?:an?\s+|the\s+)?", "", title, flags=re.I)
        title = re.sub(r"^[\W\d.)]+", "", title).strip(" -–:|")
        title = title[:1].upper() + title[1:]
        if len(title) < 6:
            continue
        if not JOB_WORDS.search(title + " " + text[:200]):
            continue
        if include and not include.search(title):
            continue
        if exclude and exclude.search(title):
            continue
        dates = [d for _, d in C.find_dates(text, dayfirst)]
        deadline = C.deadline_from_text(text, dayfirst)
        if not deadline and dates and max(dates) >= C.today():
            deadline = max(dates).isoformat()
        if not deadline and dates and max(dates) < C.today() and src.get("drop_past", True):
            continue                         # an old notice whose only dates are in the past
        if not dates and not src.get("undated_ok", True) and urlparse(href).netloc == page_host:
            continue
        seen.add(href)
        seen_blocks.add(id(block))
        out.append(posting(title[:220], href, src["name"], org=src.get("org", ""), location=src.get("location", ""),
                           description=text[:1500], deadline=deadline, hints=hints_of(src)))
    return out


def fetch_listing(src):
    out, errors = [], []
    urls = src.get("urls") or [src["url"]]
    for url in urls:
        try:
            out.extend(extract_listing(_soup(url, src), url, src))
        except Exception as e:                       # noqa: BLE001
            errors.append(e)
    if errors and len(errors) == len(urls):
        raise errors[0]
    return out
