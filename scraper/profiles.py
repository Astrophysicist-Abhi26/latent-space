"""
Research profiles: one database of positions, ranked differently per profile.

A profile never changes which positions are collected or how they are tagged; it only
turns a position's features into a 0-100 relevance score. The site recomputes the
same score in the browser (docs/score.js), so switching or tuning a profile is
instant; tests/test_profiles.py runs both and checks they agree.

Score of a position for a profile
---------------------------------
  w(tag)   weight of the most specific node in `interests` that is the tag itself or
           its field; unlisted -> ignored
  best     highest positive w over the position's topics; second = highest positive w
           from a different field
  raw    = best + cross_field * second
         + the most negative w, if any topic has one
         + kinds[kind] + sectors[sector] + labs[lab] + regions[region] + visa[visa]
         + coding   (if the role needs substantial programming)
         + senior   (if the role is senior)
         + cv  * similarity to the CV text (0-1)
         + llm * (Claude fit - 50) / 50          (only if the optional check ran)
         + network bonus (first matching organisation pattern)
  score  = round(100 * (1 - exp(-raw / 75)))    (a soft cap: strong matches never tie at 100)
  A position with no positively weighted topic scores 0. Pinned positions (watchlist,
  "Add a position" issues) score at least 60.
"""

import math
import os
import re

import yaml

import taxonomy as T
from classify import KINDS, LABS, SECTORS, VISA
from common import fold
from geo import REGIONS

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles.yaml")
LEVELS = {"top": 100, "very_high": 85, "high": 70, "medium": 45, "low": 20, "none": 0, "avoid": -40}
SOFT_CAP = 75.0
PIN_FLOOR = 60
TABLES = {"kinds": ("kind", KINDS), "sectors": ("sector", SECTORS), "labs": ("lab", LABS),
          "regions": ("region", REGIONS), "visa": ("visa", VISA)}
PROFILE_KEYS = {"label", "blurb", "interests", "cross_field", "kinds", "sectors", "labs", "regions", "coding",
                "senior", "visa", "cv", "llm", "network", "search", "needs_phd", "network_label"}


def _num(v):
    return float(LEVELS[v]) if isinstance(v, str) else float(v)


def validate(raw):
    errors = []
    profiles = (raw or {}).get("profiles") or {}
    if raw.get("default") not in profiles:
        errors.append(f"default profile {raw.get('default')!r} is not defined")
    for pid, p in profiles.items():
        if not re.fullmatch(r"[a-z0-9-]+", pid):
            errors.append(f"{pid}: ids are lower-case letters, digits and hyphens")
        for key in p:
            if key not in PROFILE_KEYS:
                errors.append(f"{pid}: unknown key {key!r}")
        if not p.get("label"):
            errors.append(f"{pid}: needs a label")
        for node, w in (p.get("interests") or {}).items():
            if node not in T.NODES:
                errors.append(f"{pid}: interest {node!r} is not a taxonomy node")
            if isinstance(w, str) and w not in LEVELS:
                errors.append(f"{pid}: {node} has unknown level {w!r}")
        for table, (_, allowed) in TABLES.items():
            for k in (p.get(table) or {}):
                if k not in allowed:
                    errors.append(f"{pid}: {table} has unknown key {k!r}")
        for pat in (p.get("network") or {}):
            try:
                re.compile(pat)
            except re.error as e:
                errors.append(f"{pid}: network pattern {pat!r}: {e}")
    return errors


def normalise(pid, p):
    return {
        "id": pid,
        "label": p["label"],
        "blurb": " ".join((p.get("blurb") or "").split()),
        "interests": {k: _num(v) for k, v in (p.get("interests") or {}).items()},
        "cross_field": float(p.get("cross_field", 0)),
        **{table: {k: float(v) for k, v in (p.get(table) or {}).items()} for table in TABLES},
        "coding": float(p.get("coding", 0)),
        "senior": float(p.get("senior", 0)),
        "needs_phd": float(p.get("needs_phd", 0)),
        "network_label": str(p.get("network_label") or "Network bonus"),
        "cv": float(p.get("cv", 0)),
        "llm": float(p.get("llm", 0)),
        "network": [[pat, float(b)] for pat, b in (p.get("network") or {}).items()],
        "search": {"terms": list((p.get("search") or {}).get("terms") or []),
                   "places": list((p.get("search") or {}).get("places") or [])},
    }


def load(path=PATH):
    """-> (default id, {id: normalised profile})"""
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    errors = validate(raw)
    if errors:
        raise ValueError("profiles.yaml: " + "; ".join(errors))
    return raw["default"], {pid: normalise(pid, p) for pid, p in raw["profiles"].items()}


def weight_for(topic, interests):
    if topic in interests:
        return interests[topic]
    return interests.get(T.field_of(topic))


def score(job, prof):
    """-> (score 0-100, reasons [[label, points], ...])"""
    weighted = []
    for t in job.get("topics") or []:
        w = weight_for(t, prof["interests"])
        if w is not None:
            weighted.append((w, T.field_of(t), t))
    pos = sorted((x for x in weighted if x[0] > 0), key=lambda x: -x[0])
    if not pos:
        return 0, []
    best = pos[0]
    raw = best[0]
    reasons = [[T.label(best[2]), best[0]]]
    second = next((x for x in pos[1:] if x[1] != best[1]), None)
    if second and prof["cross_field"]:
        pts = prof["cross_field"] * second[0]
        raw += pts
        reasons.append([T.label(second[2]) + " (second field)", pts])
    neg = min((x[0] for x in weighted if x[0] < 0), default=0)
    if neg:
        raw += neg
        reasons.append(["Topic you avoid", neg])
    for table, (key, labels) in TABLES.items():
        v = prof[table].get(job.get(key) or "")
        if v:
            raw += v
            reasons.append([labels.get(job.get(key), job.get(key)), v])
    if job.get("coding") and prof["coding"]:
        raw += prof["coding"]
        reasons.append(["Coding-heavy role", prof["coding"]])
    if job.get("level") == "senior" and prof["senior"]:
        raw += prof["senior"]
        reasons.append(["Senior role", prof["senior"]])
    if job.get("needs_phd") and prof["needs_phd"]:
        raw += prof["needs_phd"]
        reasons.append(["Needs a PhD", prof["needs_phd"]])
    cv = job.get("cv") or 0
    if prof["cv"] and cv:
        pts = prof["cv"] * cv
        raw += pts
        reasons.append(["Similar to the CV", pts])
    fit = (job.get("llm") or {}).get("fit")
    if prof["llm"] and fit is not None:
        pts = prof["llm"] * (fit - 50) / 50
        raw += pts
        reasons.append(["Claude fit check", pts])
    if prof["network"]:
        hay = fold((job.get("org") or "") + " " + (job.get("location") or ""))
        for pat, bonus in prof["network"]:
            if re.search(pat, hay):
                raw += bonus
                reasons.append([prof["network_label"], bonus])
                break
    s = math.floor(100 * (1 - math.exp(-max(raw, 0) / SOFT_CAP)) + 0.5)
    if job.get("pinned"):
        s = max(s, PIN_FLOOR)
    return min(s, 100), reasons
