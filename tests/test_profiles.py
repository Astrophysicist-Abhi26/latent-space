import json
import os
import shutil
import subprocess

import pytest

import profiles as P
import taxonomy as T
from classify import KINDS, LABS, LEVELS, SECTORS, VISA, classify
from geo import REGIONS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sample_jobs():
    base = [
        ("Research Engineer Intern, Machine Learning (Summer 2027)", "Large language model training and interpretability in PyTorch.",
         "Anthropic", "London, UK", {"sector": "ai-lab"}),
        ("Senior Backend Engineer", "Go, Postgres, Kubernetes. 6+ years of experience.", "ShopCart", "New York, NY", {}),
        ("Machine Learning Intern (weather forecasting)", "Gaussian processes and deep learning for probabilistic weather and climate "
         "forecasting; uncertainty quantification.", "Skyline Climate", "Remote", {}),
        ("Staff Research Scientist (alignment)", "PhD in machine learning required, 8+ years of experience. We are unable to sponsor visas.",
         "Frontier Labs", "San Francisco, CA", {"sector": "ai-lab"}),
        ("Postdoc in plant ecology", "Field ecology of crops and drought; Arabidopsis.", "Example University", "Uppsala, Sweden", {}),
        ("Project Associate", "Machine learning for climate data.", "IISc", "Bengaluru",
         {"keep_untagged": True, "topics": ["ml.core"]}),
    ]
    jobs = [classify({"title": t, "description": d, "org": o, "location": loc, "hints": h}) for t, d, o, loc, h in base]
    jobs[0].update(cv=0.5, llm={"fit": 88, "why": "x"})
    jobs[2].update(cv=0.62, llm={"fit": 92, "why": "y"})
    jobs[5].update(pinned=True)
    return jobs


def test_profiles_yaml_is_valid():
    default, profs = P.load()
    assert default == "kartik" and {"labs", "india", "science", "quant", "explore"} <= set(profs)


def test_kartiks_ranking():
    _, profs = P.load()
    jobs = sample_jobs()
    s = {j["title"]: P.score(j, profs["kartik"])[0] for j in jobs}
    intern, climate = s["Research Engineer Intern, Machine Learning (Summer 2027)"], s["Machine Learning Intern (weather forecasting)"]
    staff = s["Staff Research Scientist (alignment)"]
    assert intern >= 80 and climate >= 80 and intern > staff and climate > staff
    assert s["Senior Backend Engineer"] < 30 and s["Postdoc in plant ecology"] < 20 and s["Project Associate"] >= P.PIN_FLOOR
    assert jobs[3]["needs_phd"] and not jobs[0]["needs_phd"]
    lab = {j["title"]: P.score(j, profs["labs"])[0] for j in jobs}
    sci = {j["title"]: P.score(j, profs["science"])[0] for j in jobs}
    assert lab["Research Engineer Intern, Machine Learning (Summer 2027)"] >= lab["Machine Learning Intern (weather forecasting)"]
    assert sci["Machine Learning Intern (weather forecasting)"] >= sci["Research Engineer Intern, Machine Learning (Summer 2027)"]


def test_reasons_explain_the_score():
    _, profs = P.load()
    jobs = sample_jobs()
    labels = [r[0] for r in P.score(jobs[0], profs["kartik"])[1]]
    for want in ("Internship / summer project", "Frontier AI lab", "Europe (incl. UK, CH, NO)", "Similar to the CV", "Claude fit check"):
        assert want in labels, want
    assert "Needs a PhD" in [r[0] for r in P.score(jobs[3], profs["kartik"])[1]]
    assert "Near Pune or Bengaluru" in [r[0] for r in P.score(jobs[5], profs["kartik"])[1]]


def test_off_topic_scores_zero():
    _, profs = P.load()
    assert P.score({"topics": ["org.plant"], "kind": "postdoc"}, profs["quant"])[0] == 0


def test_browser_and_python_scores_agree():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    _, profs = P.load()
    profiles = list(profs.values()) + [P.normalise("t", {"label": "t", "interests": {"micro": 50, "org": "avoid"},
                                                          "cross_field": 0.3, "senior": -5, "coding": -9})]
    jobs = sample_jobs()
    ctx = {"taxonomy": {"fields": T.FIELDS, "subfields": {k: {"label": v[0], "field": T.field_of(k)}
                                                          for k, v in T.SUBFIELDS.items()}},
           "labels": {"kinds": KINDS, "sectors": SECTORS, "labs": LABS, "visa": VISA, "levels": LEVELS, "regions": REGIONS},
           "soft_cap": P.SOFT_CAP, "pin_floor": P.PIN_FLOOR}
    script = ("const S = require(%s); const d = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
              "const c = S.makeContext(d.ctx);"
              "console.log(JSON.stringify(d.profiles.map(p => d.jobs.map(j => S.scoreJob(j, p, c)))));"
              % json.dumps(os.path.join(ROOT, "docs", "score.js")))
    out = subprocess.run([node, "-e", script], input=json.dumps({"jobs": jobs, "profiles": profiles, "ctx": ctx}),
                         capture_output=True, text=True, check=True)
    js = json.loads(out.stdout)
    for p, row in zip(profiles, js):
        for j, res in zip(jobs, row):
            score, reasons = P.score(j, p)
            assert res["score"] == score, (p["id"], j["title"])
            assert [[a, round(b, 9)] for a, b in res["reasons"]] == [[a, round(b, 9)] for a, b in reasons]
