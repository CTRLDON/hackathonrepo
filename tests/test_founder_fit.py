"""Founder Fit: founder-specific verdicts from the founder's own answers, no model."""
from services import founder_fit


def test_coder_with_time_builds_it_and_insights_quote_the_founder():
    v = {"idea": "A web app that turns designer call notes into project briefs", "brief": {}}
    r = founder_fit.assess(v, {"skills": "I code in Python", "available_time": "10 hours a week",
                               "budget": "$300", "values": "honest pricing"})
    assert r["verdict"] == "build"
    assert any('"10 hours a week"' in i and "8 weeks" in i for i in r["insights"])
    assert any("honest pricing" in i for i in r["insights"])


def test_non_coder_with_software_idea_should_partner_up():
    v = {"idea": "An AI study companion app for students", "brief": {}}
    r = founder_fit.assess(v, {"skills": "marketing and sales", "available_time": "5 hours a week", "budget": "50"})
    assert r["verdict"] in ("partner", "narrow")
    assert any("technical co-founder" in x for x in r["reasons"])


def test_stop_gate_and_missing_answers_are_handled():
    assert founder_fit.assess({"idea": "x", "gate": "STOP"}, {})["verdict"] == "stop"
    r = founder_fit.assess({"idea": "A newsletter", "brief": {}}, {})
    assert r["verdict"] == "unknown" and r["insights"]


def test_founder_fit_endpoint():
    from fastapi.testclient import TestClient
    from backend import app as app_mod
    c = TestClient(app_mod.app)
    v = c.post("/api/ventures", json={"idea": "A web app for freelance designers"}).json()
    c.post(f"/api/ventures/{v['id']}/update-field", json={"field": "available_time", "value": "20 hours a week"})
    r = c.get(f"/api/ventures/{v['id']}/founder-fit").json()
    assert r["label"] and any("20 hours a week" in i for i in r["insights"])
