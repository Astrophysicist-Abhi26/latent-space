import json

import common as C
import llm_fit
from offline import FakeResponse


def test_parse_reads_json_even_inside_a_code_fence():
    got = llm_fit._parse('```json\n{"lab": "wet", "coding_required": false, "visa": "unknown", "fit": 87, "why": "AMR bench work"}\n```')
    assert got == {"lab": "wet", "coding": False, "visa": "unknown", "fit": 87, "why": "AMR bench work"}
    assert llm_fit._parse("no json here") is None


def test_label_jobs_calls_claude_once_and_caches(tmp_path, monkeypatch):
    calls = []

    class Fake:
        def post(self, url, **kw):
            calls.append(kw["json"]["model"])
            text = json.dumps({"lab": "wet", "coding_required": False, "visa": "sponsors", "fit": 80, "why": "Good AMR fit"})
            return FakeResponse(url, 200, json.dumps({"content": [{"type": "text", "text": text}]}), "application/json")

    monkeypatch.setattr(C, "HTTP", Fake())
    monkeypatch.setattr(llm_fit, "CACHE", str(tmp_path / "llm.json"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    job = {"id": "abc", "title": "Postdoc AMR", "description": "bench", "lab": "unknown", "visa": "unknown"}
    status = llm_fit.label_jobs([job], [job])
    assert status["status"] == "ok" and job["llm"]["fit"] == 80 and job["lab"] == "wet" and job["visa"] == "sponsors"
    again = {"id": "abc", "title": "Postdoc AMR", "description": "bench"}
    llm_fit.label_jobs([again], [again])
    assert len(calls) == 1 and again["llm"]["why"] == "Good AMR fit"


def test_without_a_key_nothing_is_sent(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(llm_fit, "CACHE", str(tmp_path / "llm.json"))
    assert llm_fit.label_jobs([{"id": "x", "title": "t"}], [])["status"] == "off"
