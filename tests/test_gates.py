def test_validate_gate_repeats_without_results():
    from backend import gates
    assert gates.validate_gate([]) == "REPEAT"


def test_no_stage_runs_while_a_decision_is_pending():
    from fastapi.testclient import TestClient
    from backend import app as app_mod, approval
    from memory import database
    c = TestClient(app_mod.app)
    v = c.post("/api/ventures", json={"idea": "An AI study companion"}).json()
    database.set_stage_status(v["id"], "discover", "stopped")
    approval.request(v["id"], "discover_gate", {"recommendation": "STOP"})
    r = c.post(f"/api/ventures/{v['id']}/run-stage/discover").json()
    assert r["status"] == "already_ran"

def test_orchestrator_has_all_stages():
    from backend.orchestrator import Orchestrator
    try:
        o = Orchestrator()
    except Exception:
        import pytest; pytest.skip("model unavailable")
    for m in ("run_discover", "run_validate", "run_build",
              "run_commercial", "run_launch", "run_operate"):
        assert hasattr(o, m)
