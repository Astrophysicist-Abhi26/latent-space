"""
Company job boards (companies.yaml), read through the public APIs the boards publish
for exactly this purpose:

  greenhouse  https://boards-api.greenhouse.io/v1/boards/<slug>/jobs?content=true
  lever       https://api.lever.co/v0/postings/<slug>?mode=json   (eu: api.eu.lever.co)
  ashby       https://api.ashbyhq.com/posting-api/job-board/<slug>
  workable    https://apply.workable.com/api/v1/widget/accounts/<slug>?details=true
  workday     the JSON search behind <host>/<site> (robots.txt is honoured)

A company board lists every role (software, sales, finance ...); the pipeline keeps
only biology research roles. probe(slug) finds which board a company is on, for
`python scraper/doctor.py --probe <slug>`.
"""

import datetime as dt
import re

import common as C
from sources_feeds import posting
import taxonomy as T

GROUP_SECTOR = {"ai-lab": "ai-lab", "tech": "tech", "quant": "quant", "ai-bio": "ai-bio", "biotech": "biotech", "pharma": "pharma", "nonprofit": "nonprofit",
                "institute": "academic"}


def _hints(c):
    h = {"sector": GROUP_SECTOR.get(c.get("group", "biotech"), "industry")}
    if c.get("country"):
        h["country"] = c["country"]
    return h


def greenhouse(c):
    data = C.get(f"https://boards-api.greenhouse.io/v1/boards/{c['slug']}/jobs?content=true", feed=True).json()
    out = []
    for j in data.get("jobs", []):
        loc = (j.get("location") or {}).get("name", "")
        offices = ", ".join(o.get("name", "") for o in j.get("offices") or [] if o.get("name"))
        out.append(posting(
            j.get("title", ""), j.get("absolute_url", ""), c["name"], org=c["name"], location=loc or offices,
            description=C.html_text(j.get("content", "")),
            posted=C.parse_date(j.get("first_published") or j.get("updated_at")), hints=_hints(c)))
    return out


def lever(c):
    base = "https://api.eu.lever.co" if c.get("eu") else "https://api.lever.co"
    data = C.get(f"{base}/v0/postings/{c['slug']}?mode=json", feed=True).json()
    out = []
    for j in data if isinstance(data, list) else []:
        cat = j.get("categories") or {}
        lists = " ".join(f"{x.get('text', '')}: {C.html_text(x.get('content', ''))}" for x in j.get("lists") or [])
        desc = " ".join(x for x in (j.get("descriptionPlain", ""), lists, j.get("additionalPlain", "")) if x)
        loc = cat.get("location") or ", ".join(cat.get("allLocations") or [])
        out.append(posting(
            j.get("text", ""), j.get("hostedUrl", ""), c["name"], org=c["name"], location=loc, description=desc,
            posted=C.parse_date(j.get("createdAt")), apply_url=j.get("applyUrl", ""), hints=_hints(c)))
    return out


def ashby(c):
    data = C.get(f"https://api.ashbyhq.com/posting-api/job-board/{c['slug']}?includeCompensation=true", feed=True).json()
    out = []
    for j in data.get("jobs", []):
        if j.get("isListed") is False:
            continue
        locs = [j.get("location") or ""] + [x.get("location", "") for x in j.get("secondaryLocations") or []]
        if j.get("isRemote"):
            locs.append("Remote")
        out.append(posting(
            j.get("title", ""), j.get("jobUrl", ""), c["name"], org=c["name"], location=", ".join(x for x in locs if x),
            description=j.get("descriptionPlain") or C.html_text(j.get("descriptionHtml", "")),
            posted=C.parse_date(j.get("publishedAt")), apply_url=j.get("applyUrl", ""), hints=_hints(c)))
    return out


def workable(c):
    data = C.get(f"https://apply.workable.com/api/v1/widget/accounts/{c['slug']}?details=true", feed=True).json()
    out = []
    for j in data.get("jobs", []):
        loc = ", ".join(x for x in (j.get("city"), j.get("state"), j.get("country")) if x)
        if not loc and j.get("locations"):
            first = j["locations"][0]
            loc = ", ".join(x for x in (first.get("city"), first.get("country")) if x)
        out.append(posting(
            j.get("title", ""), j.get("url") or j.get("shortlink", ""), c["name"], org=c["name"], location=loc,
            description=C.html_text(j.get("description", "")),
            posted=C.parse_date(j.get("published_on") or j.get("created_at")),
            apply_url=j.get("application_url", ""), hints=_hints(c)))
    return out


_POSTED_ON = re.compile(r"posted\s+(today|yesterday|(\d+)\+?\s+days?\s+ago)", re.I)


def _workday_posted(text):
    m = _POSTED_ON.search(text or "")
    if not m:
        return None
    if m.group(1).lower() == "today":
        days = 0
    elif m.group(1).lower() == "yesterday":
        days = 1
    else:
        days = int(m.group(2))
    return (C.today() - dt.timedelta(days=days)).isoformat()


def workday(c):
    base = f"https://{c['host']}/wday/cxs/{c['tenant']}/{c['site']}"
    out, seen, details = [], set(), 0
    for q in c.get("queries") or [""]:
        data = C.post_json(base + "/jobs", {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": q}).json()
        for j in data.get("jobPostings") or []:
            path = j.get("externalPath") or ""
            if not path or path in seen:
                continue
            seen.add(path)
            title = j.get("title", "")
            desc = ""
            if details < int(c.get("max_details", 25)) and T.tag(title, ""):
                try:
                    info = C.get(base + path, headers={"Accept": "application/json"}).json().get("jobPostingInfo") or {}
                    desc = C.html_text(info.get("jobDescription", ""))
                    details += 1
                except Exception:
                    pass
            out.append(posting(
                title, f"https://{c['host']}/{c['site']}{path}", c["name"], org=c["name"],
                location=j.get("locationsText", ""), description=desc, posted=_workday_posted(j.get("postedOn")),
                hints=_hints(c)))
    return out


ADAPTERS = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby, "workable": workable, "workday": workday}


def fetch_company(c):
    return ADAPTERS[c["ats"]](c)


def probe(slug):
    """Which public job board answers for this slug? -> [(ats, number of jobs or error)]"""
    results = []
    for ats in ("greenhouse", "lever", "ashby", "workable"):
        try:
            jobs = ADAPTERS[ats]({"name": slug, "slug": slug})
            results.append((ats, len(jobs)))
        except Exception as e:                                   # noqa: BLE001
            results.append((ats, f"{type(e).__name__}: {str(e)[:80]}"))
    return results
