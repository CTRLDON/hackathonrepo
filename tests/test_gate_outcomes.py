"""Gates recommend; the founder decides. Nothing moves without a recorded founder choice."""
from fastapi.testclient import TestClient

from backend import approval_manager, gates
from backend import app as app_mod
from memory import database

client = TestClient(app_mod.app)


def test_waitlist_gate_fails_on_weak_demand():
    # The problem statement's example: target 100 sign-ups in 14 days, got 12 → don't spin it.
    r = gates.waitlist_gate(12)
    assert r["outcome"] == "STOP" and r["target"] == 100 and r["days"] == 14
    assert gates.waitlist_gate(30)["outcome"] == "PIVOT"
    assert gates.waitlist_gate(60)["outcome"] == "REPEAT"
    assert gates.waitlist_gate(100)["outcome"] == "GO"


def test_phase_gates():
    assert gates.discover_gate({"gate_recommendation": "STOP"}) == "STOP"
    assert gates.discover_gate({}) == "REPEAT"
    assert gates.validate_gate([{"verdict": "contradicted"}, {"verdict": "supported"}]) == "PIVOT"
    assert gates.validate_gate([{"verdict": "supported"}, {"verdict": "unverified"}]) == "GO"
    assert gates.build_gate(True, 2) == "REPEAT" and gates.build_gate(True, 3) == "GO"
    assert gates.commercial_gate(15) == "REPEAT" and gates.commercial_gate(45) == "GO"
    assert gates.launch_gate(["Best in the world"]) == "REPEAT"


def _venture_at(stage, recommendation):
    v = client.post("/api/ventures", json={"idea": "An AI study companion"}).json()
    database.update_venture(v["id"], current_stage=stage, brief={"name": "X"})
    database.set_stage_status(v["id"], stage, "awaiting_approval")
    aid = approval_manager.request(v["id"], f"{stage}_gate", {"recommendation": recommendation})
    return v["id"], aid


def _choose(vid, aid, choice):
    return client.post("/api/approve", json={"venture_id": vid, "approval_id": aid, "choice": choice})


def test_stop_choice_stops_instead_of_advancing():
    vid, aid = _venture_at("discover", "STOP")
    r = _choose(vid, aid, "stop").json()
    assert r["choice"] == "stop" and not r["override"]
    v = database.get_venture(vid)
    assert v["current_stage"] == "discover" and database.get_stages(vid)["discover"]["status"] == "stopped"


def test_continue_against_stop_is_a_logged_override():
    vid, aid = _venture_at("discover", "STOP")
    r = _choose(vid, aid, "continue").json()
    assert r["override"] and r["advanced_to"] == "validate"
    log = client.get(f"/api/ventures/{vid}/decisions").json()
    assert any("override" in d["action"] and d["approval_status"] == "approved" for d in log)


def test_pivot_goes_back_one_phase_and_repeat_reruns():
    vid, aid = _venture_at("validate", "PIVOT")
    assert _choose(vid, aid, "pivot").json()["advanced_to"] == "discover"
    assert database.get_venture(vid)["current_stage"] == "discover"
    assert database.get_stages(vid)["validate"]["status"] == "not_started"

    vid, aid = _venture_at("build", "REPEAT")
    _choose(vid, aid, "repeat")
    assert database.get_stages(vid)["build"]["status"] == "awaiting_input"


def test_no_choice_without_a_pending_approval():
    vid, aid = _venture_at("discover", "GO")
    assert _choose(vid, aid, "continue").status_code == 200
    assert _choose(vid, aid, "continue").status_code == 400  # already resolved
    assert _choose(vid, "not-an-approval", "continue").status_code == 400


def test_demand_test_records_real_numbers():
    vid, _ = _venture_at("validate", "GO")
    r = client.post(f"/api/ventures/{vid}/demand-test", json={"signups": 12}).json()
    assert r["outcome"] == "STOP" and r["reported_by"] == "founder"
    assert client.post(f"/api/ventures/{vid}/demand-test", json={"signups": -5}).status_code == 400


def test_pre_registered_target_is_used_and_then_locked():
    vid, _ = _venture_at("validate", "GO")
    assert client.post(f"/api/ventures/{vid}/demand-target", json={"signups": 50, "days": 10}).status_code == 200
    r = client.post(f"/api/ventures/{vid}/demand-test", json={"signups": 30}).json()
    assert r["target"] == 50 and r["days"] == 10 and r["outcome"] == "REPEAT" and r["target_set_by"] == "founder"
    # No moving the goalposts after seeing the data.
    assert client.post(f"/api/ventures/{vid}/demand-target", json={"signups": 25, "days": 10}).status_code == 409
    assert client.post(f"/api/ventures/{vid}/demand-target", json={"signups": 0, "days": 10}).status_code == 400
