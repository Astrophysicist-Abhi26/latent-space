"""
Positions added by hand.

  watchlist.yaml       pinned entries you edit in the repository
  "Add a position"     GitHub issues opened with the form in .github/ISSUE_TEMPLATE/
                       (label add-position). An open issue is listed; closing it removes
                       the position at the next run. This is the route for postings found
                       on LinkedIn, X, mailing lists or by word of mouth.

Both are pinned: they always appear, with a score of at least 60 where relevant.
"""

import os
import re

import yaml

import common as C
from sources_feeds import posting

ROOT = os.path.dirname(os.path.abspath(__file__))
WATCHLIST = os.path.join(ROOT, "watchlist.yaml")
FORM_FIELDS = {"position title": "title", "link to the posting": "url", "organisation": "org",
               "organization": "org", "location": "location", "application deadline": "deadline",
               "type of position": "kind", "notes": "notes"}
KIND_WORDS = {"phd": "phd", "internship": "internship", "intern": "internship", "postdoc": "postdoc", "fellowship": "fellowship", "scientist": "scientist", "industry": "scientist",
              "technician": "technician", "assistant": "technician", "faculty": "faculty"}


def _kind(text):
    t = (text or "").lower()
    return next((v for k, v in KIND_WORDS.items() if k in t), None)


def _pinned(title, url, source, org, location, deadline, notes, kind=None, extra=None):
    hints = {"keep_untagged": True, "topics": ["life.general"]}
    if kind:
        hints["kind"] = kind
    j = posting(title, url, source, org=org, location=location, description=notes or "",
                deadline=C.parse_date(deadline) if deadline else None, hints=hints, pinned=True)
    j.update(extra or {})
    return j


def fetch_watchlist(path=WATCHLIST):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    out = []
    for e in data.get("positions") or []:
        if not e.get("title") or not e.get("url"):
            continue
        out.append(_pinned(e["title"], e["url"], "Watchlist", e.get("org", ""), e.get("location", ""),
                           e.get("deadline"), e.get("notes", ""), _kind(e.get("kind"))))
    return out


def parse_issue_form(body):
    """GitHub issue-form markdown ("### Heading\\n\\nvalue") -> dict of known fields."""
    out = {}
    for section in re.split(r"^###\s+", body or "", flags=re.M)[1:]:
        head, _, value = section.partition("\n")
        key = FORM_FIELDS.get(head.strip().lower())
        value = value.strip()
        if key and value and value != "_No response_":
            out[key] = value
    return out


def fetch_issues(repo=None, token=None):
    repo = repo or os.environ.get("GITHUB_REPOSITORY")
    token = token or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not repo:
        return []
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"https://api.github.com/repos/{repo}/issues?labels=add-position&state=open&per_page=100"
    issues = C.get(url, feed=True, headers=headers).json()
    out = []
    for issue in issues if isinstance(issues, list) else []:
        f = parse_issue_form(issue.get("body", ""))
        url = (re.search(r"https?://\S+", f.get("url", "")) or [None])[0]
        title = f.get("title") or re.sub(r"^\[add\]\s*", "", issue.get("title", ""), flags=re.I)
        if not url or not title:
            continue
        out.append(_pinned(title, url.rstrip(").,>"), "Added by you", f.get("org", ""), f.get("location", ""),
                           f.get("deadline"), f.get("notes", ""), _kind(f.get("kind")),
                           {"issue": issue.get("html_url", "")}))
    return out
