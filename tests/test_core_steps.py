"""Core steps from the problem statement: find opportunities (Discover), user docs (Build),
launch posts (Launch), support + persevere-or-pivot memo (Operate)."""
import pytest

from agents.opportunity_agent import weighted_score

GOOD = {"pain": 5, "founder_fit": 4, "reach": 3, "buildable": 5, "gap": 2}


class Stub:
    model = "stub"

    def ensure_ready(self):
        pass

    def chat(self, messages, **kw):
        raise RuntimeError("no html in this test")  # Build uses its template fallback

    def chat_json(self, messages, *, system, schema_hint=None, temperature=0.2):
        h = schema_hint or ""
        if '"options"' in h:
            return {"options": [
                {"title": "Original planner", "description": "the founder's idea", "is_original": True,
                 "scores": {"pain": 3, "founder_fit": 3, "reach": 3, "buildable": 3, "gap": 3}, "reasons": "ok"},
                {"title": "Exam pack for engineers", "description": "narrower segment", "is_original": False,
                 "scores": GOOD, "reasons": "ASSUMPTION: strong pain"},
                {"title": "Printed planner shop", "description": "sell physical goods: printed planners",
                 "is_original": False, "scores": GOOD, "reasons": "x"},  # excluded product -> filtered
            ]}
        if '"posts"' in h:
            return {"posts": [
                {"channel": "linkedin", "audience": "students", "text": "We built a planner. Feedback welcome!"},
                {"channel": "x", "audience": "students", "text": "Guaranteed to earn you $5000 a month!"},
            ]}
        if '"faq"' in h:
            return {"faq": [{"q": "Can I get a refund?", "a": "Yes, within 14 days — the founder handles it."}],
                    "reply_templates": [{"situation": "Bug report", "reply": "Thanks — we're on it."}]}
        if '"recommendation"' in h:
            return {"recommendation": "pivot", "summary": "Demand is unproven.",
                    "evidence_for_persevering": ["Clear pain"], "evidence_against": ["No sign-ups yet"],
                    "what_would_change_our_mind": ["100 waitlist sign-ups in 14 days"]}
        if '"features"' in h:
            return {"features": [{"name": "Plan", "purpose": "plan study", "acceptance": "plan shown"},
                                 {"name": "Quiz", "purpose": "practice", "acceptance": "quiz runs"},
                                 {"name": "Streaks", "purpose": "habit", "acceptance": "streak shown"}],
                    "out_of_scope": ["Mobile app"]}
        if '"kpis"' in h:
            return {"kpis": [{"metric": "Weekly actives", "target_90_days": "200", "how_to_measure": "logs"}],
                    "roadmap": {"days_0_30": ["Beta"]}, "risks": [], "first_action_tomorrow": "Email 10 students"}
        return {}


@pytest.fixture
def orch(monkeypatch, tmp_path):
    from backend import app as app_mod
    from backend import orchestrator as orch_mod
    from tools import web_search
    stub = Stub()
    for agent in vars(app_mod.orchestrator).values():
        if hasattr(agent, "client"):
            monkeypatch.setattr(agent, "client", stub)
    monkeypatch.setattr(orch_mod, "OUTPUTS_DIR", tmp_path)
    monkeypatch.setattr(web_search, "search", lambda q, max_results=6: {
        "results": [{"title": "t", "url": "https://ex.com/a", "snippet": "s"}], "error": None, "query_used": q})
    return app_mod.orchestrator, tmp_path


def _venture_at(stage):
    from memory import database
    from config import STAGES
    v = database.create_venture(name="StudyBuddy", idea="AI study planner for university students")
    database.update_venture(v["id"], brief={"name": "StudyBuddy", "assumptions": ["Students will pay"]},
                            current_stage=stage)
    for s in STAGES[:STAGES.index(stage)]:
        database.set_stage_status(v["id"], s, "completed")
    return v["id"]


def test_weighted_score_is_computed_in_code_and_clamped():
    assert weighted_score(GOOD) == round(.3 * 5 + .25 * 4 + .15 * 3 + .15 * 5 + .15 * 2, 2)
    assert weighted_score({"pain": 99, "founder_fit": -3}) == 1.5  # clamped to 0..5


def test_discover_scores_idea_against_alternatives(orch):
    o, out = orch
    vid = _venture_at("discover")
    res = o.run_stage(vid, "discover")
    sec = {s["title"]: s["items"] for s in res["report"]["sections"]}
    lines = next(v for k, v in sec.items() if k.startswith("Opportunities scored"))
    assert lines[0].startswith("4.0/5 — Exam pack")                 # ranked by computed score
    assert any("(your original idea)" in l for l in lines)
    assert not any("Printed planner" in l for l in lines)           # excluded product filtered out
    md = (out / vid / "discover" / "opportunities.md").read_text()
    assert "ASSUMPTION" in md and "founder chooses" in md.lower()


def test_build_writes_user_guide(orch):
    o, out = orch
    vid = _venture_at("build")
    o.run_stage(vid, "build")
    guide = (out / vid / "mvp" / "USER_GUIDE.md").read_text()
    assert "## Getting started" in guide and "### 3. Streaks" in guide and "Mobile app" in guide


def test_launch_posts_are_drafts_and_guardrailed(orch):
    o, out = orch
    vid = _venture_at("launch")
    o.run_stage(vid, "launch")
    md = (out / vid / "launch" / "launch_posts.md").read_text()
    assert "DRAFTS — not posted" in md and "Feedback welcome" in md
    assert "$5000" not in md.split("Blocked by guardrails")[0]       # income promise never usable
    assert "Blocked by guardrails" in md


def test_operate_writes_support_kit_and_pivot_memo(orch):
    o, out = orch
    vid = _venture_at("operate")
    res = o.run_stage(vid, "operate")
    hl = {h["label"]: h["value"] for h in res["report"]["highlights"]}
    assert hl["Memo recommends"].startswith("Pivot")
    memo = (out / vid / "final" / "persevere_or_pivot_memo.md").read_text()
    assert "Recommendation: PIVOT" in memo and "founder decides" in memo and "100 waitlist" in memo
    kit = (out / vid / "final" / "support_kit.md").read_text()
    assert "Can I get a refund?" in kit and "never sends" in kit
