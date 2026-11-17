"""The founder brief covers skills, budget, available time, target market and values."""
from fastapi.testclient import TestClient

from backend import app as app_mod

client = TestClient(app_mod.app)


def test_available_time_and_values_reach_the_brief_inputs():
    v = client.post("/api/ventures", json={"idea": "A web app for freelance designers"}).json()
    for field, value in (("available_time", "10 hours a week for 3 months"), ("values", "honest pricing")):
        r = client.post(f"/api/ventures/{v['id']}/update-field", json={"field": field, "value": value})
        assert r.status_code == 200, r.text
    answers = client.get(f"/api/ventures/{v['id']}/summary").json()["answers"]
    assert answers["available_time"] == "10 hours a week for 3 months"
    assert answers["values"] == "honest pricing"
    assert client.post(f"/api/ventures/{v['id']}/update-field",
                       json={"field": "password", "value": "x"}).status_code == 400
