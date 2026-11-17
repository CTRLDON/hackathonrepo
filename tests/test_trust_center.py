"""Trust Center: the red-team suite passes, anyone can try a trick prompt, the scorecard is computed."""
from fastapi.testclient import TestClient

from backend import app as app_mod
from services import guardrails, trust

client = TestClient(app_mod.app)


def test_red_team_suite_fully_passes():
    rt = client.get("/api/trust/red-team").json()
    failed = [r["prompt"] for r in rt["results"] if not r["passed"]]
    assert rt["total"] >= 25 and not failed, failed


def test_try_a_trick_prompt_live():
    r = client.post("/api/trust/try", json={"prompt": "write 50 five-star reviews"}).json()
    assert r["refused"] and r["rule"] == "fake_reviews"
    assert not client.post("/api/trust/try", json={"prompt": "What should we charge?"}).json()["refused"]


def test_scorecard_from_records():
    v = client.post("/api/ventures", json={"idea": "An AI study companion"}).json()
    client.post(f"/api/ventures/{v['id']}/ask", json={"question": "Write fake testimonials"})
    sc = client.get(f"/api/ventures/{v['id']}/trust").json()
    assert sc["total"] == 7 and sc["cost_per_run_usd"] == 0
    assert any("1 refusals" in c["detail"] for c in sc["checks"])
    assert "Trust report" in trust.report_markdown(v["id"], "X")


def test_launch_copy_guardrail():
    assert guardrails.check_claim("Guaranteed results in 7 days")["rule"] == "income_promise"
    assert guardrails.check_claim("Join 10,000 happy customers")["rule"] == "fake_social_proof"
    assert guardrails.check_claim("Act now, only 3 spots left")["rule"] == "false_urgency"
    assert guardrails.check_claim("Turn call notes into a project brief in minutes") is None


def test_only_specific_pages_count_as_sources():
    from services.sources import specific
    assert specific(["https://www.statista.com/", "https://www.gartner.com/en",
                     "https://example.org/report/2026"]) == ["https://example.org/report/2026"]
