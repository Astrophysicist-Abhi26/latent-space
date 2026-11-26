import json

import common as C
import offline
import scrape as S

GONE = ["Senior Backend Engineer", "Lecturer in Accounting", "Postdoc in microbial ecology of soils",
        "PhD position in bacterial cell biology", "Software Engineer, Infrastructure"]


def run(tmp_path, monkeypatch, name="jobs.json"):
    monkeypatch.setattr(C, "HTTP", C.HTTP)          # undone after the test
    monkeypatch.setattr(C, "HOST_GAP", 0)
    out = tmp_path / name
    assert S.main(["--offline", "--out", str(out), "--notify", str(tmp_path / "notify"), "--no-llm", "--workers", "4"]) == 0
    return out, json.loads(out.read_text())


def test_offline_run_builds_the_site_data(tmp_path, monkeypatch):
    _, d = run(tmp_path, monkeypatch)
    titles = {j["title"] for j in d["jobs"]}
    assert d["sample"] is True and d["profiles"]["default"] == "kartik" and d["programmes"]
    for kept in ("Research Engineer Intern, Machine Learning (Summer 2027)", "Anthropic Fellows Program — AI Safety Fellow",
                 "ML Research Engineer (LLMs, Indic languages)", "Machine Learning Intern (weather forecasting)",
                 "Quantitative Researcher (new grad)"):
        assert kept in titles, kept
    assert not any(j["kind"] in ("phd", "postdoc", "faculty") for j in d["jobs"])
    for gone in GONE:
        assert gone not in titles, gone
    top = d["jobs"][0]
    assert top["kind"] in ("internship", "fellowship") and any(t.startswith(("ml.", "sci.", "ds.")) for t in top["topics"])
    for j in d["jobs"]:
        assert {"id", "title", "url", "kind", "sector", "lab", "region", "topics", "first_seen", "summary"} <= set(j)
    assert len(d["health"]) == len(S.build_sources())
    hn = next(h for h in d["health"] if h["name"].startswith("Hacker News"))
    assert hn["status"] in ("ok", "low") and hn["kept"] >= 4
    assert (tmp_path / "notify" / "digest.md").read_text().startswith("### ")


def test_first_seen_survives_and_a_broken_source_is_carried(tmp_path, monkeypatch):
    out, d = run(tmp_path, monkeypatch)
    d["sample"] = False                                # pretend it was a real deployed run
    ant = next(j for j in d["jobs"] if j["title"] == "Research Engineer Intern, Machine Learning (Summer 2027)")
    ant["first_seen"] = "2026-11-01"
    out.write_text(json.dumps(d))
    monkeypatch.setattr(offline, "ROUTES", [("GET", r"boards/anthropic\b", "missing.json")] + offline.ROUTES)
    _, d2 = run(tmp_path, monkeypatch)
    health = {h["name"]: h for h in d2["health"]}
    assert health["Anthropic"]["status"] == "error" and health["Anthropic"]["carried"] >= 1
    t2 = next(j for j in d2["jobs"] if j["title"] == "Research Engineer Intern, Machine Learning (Summer 2027)")
    assert t2["carried"] and t2["first_seen"] == "2026-11-01"
