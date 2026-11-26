#!/usr/bin/env python3
"""
Posts notify/digest.md (written by scrape.py) as a comment on the repository's open issue
labelled "digest", creating that issue the first time. Watch the issue on GitHub (or have
Kartik watch it) to receive each day's new matches and broken-source alerts by e-mail.

Always exits 0: a digest that cannot be posted must never fail the daily run.
"""

import os
import sys

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "notify", "digest.md")
API = "https://api.github.com"
INTRO = ("Latent Space posts a comment here each day with new positions that match Kartik's profile "
         "well, and with any source that stopped working.\n\n"
         "Click **Subscribe** (or *Watch → Custom → Issues*) to get these comments by e-mail.")


def main():
    try:
        with open(PATH, encoding="utf-8") as f:
            body = f.read().strip()
    except FileNotFoundError:
        body = ""
    if not body:
        print("digest: nothing new today")
        return 0
    repo = os.environ.get("GITHUB_REPOSITORY")
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not repo or not token:
        print("digest: no repository or token (local run); not posted:\n")
        print(body)
        return 0
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
    try:
        r = s.get(f"{API}/repos/{repo}/issues", params={"labels": "digest", "state": "open", "per_page": 1}, timeout=30)
        r.raise_for_status()
        issues = r.json()
        if issues:
            number = issues[0]["number"]
        else:
            r = s.post(f"{API}/repos/{repo}/issues", timeout=30,
                       json={"title": "Daily digest: new PhD positions and internships for Kartik", "body": INTRO, "labels": ["digest"]})
            r.raise_for_status()
            number = r.json()["number"]
        s.post(f"{API}/repos/{repo}/issues/{number}/comments", json={"body": body}, timeout=30).raise_for_status()
        print(f"digest posted to issue #{number}")
    except Exception as e:                                     # noqa: BLE001
        print(f"digest not posted: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
