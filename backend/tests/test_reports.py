"""Community incident reports: anonymous submission, map listing, patrol status updates."""

import pytest

from app.config import settings

# T1 is at (-26.25, 27.85) in the test data; this point is ~100 m away.
NEAR_T1 = {"lat": -26.2509, "lon": 27.8505}


def submit(client, **overrides):
    body = {"category": "cable_theft", **NEAR_T1, "is_urgent": True, **overrides}
    return client.post("/reports", json=body)


@pytest.fixture
def patrol_code(monkeypatch):
    monkeypatch.setattr(settings, "patrol_code", "street-watch")
    return "street-watch"


def test_submit_report_returns_reference_and_nearest_transformer(client):
    response = submit(client, description="  Cables cut behind the clinic  ")
    assert response.status_code == 201
    body = response.json()
    assert len(body["id"]) == 6 and body["id"].isalnum()
    assert body["transformer_id"] == "T1"
    assert body["status"] == "new"
    assert body["description"] == "Cables cut behind the clinic"
    assert body["created_at"]


def test_report_far_from_any_transformer_has_no_link(client):
    body = submit(client, lat=-26.35, lon=27.95).json()
    assert body["transformer_id"] is None


def test_reports_are_anonymous(client):
    response = submit(client, name="Thabo", phone="0821234567")
    assert response.status_code == 201
    assert "name" not in response.json() and "phone" not in response.json()


@pytest.mark.parametrize(
    "overrides",
    [
        {"category": "noise_complaint"},
        {"lat": -33.9, "lon": 18.4},  # Cape Town: outside the service area
        {"description": "x" * 501},
    ],
)
def test_invalid_reports_are_rejected(client, overrides):
    assert submit(client, **overrides).status_code == 422


def test_open_reports_are_listed_urgent_first(client):
    submit(client, category="outage", is_urgent=False)
    submit(client, category="sparking", is_urgent=True)
    listed = client.get("/reports").json()
    assert [r["category"] for r in listed] == ["sparking", "outage"]


def test_report_counts_show_on_the_transformer(client):
    submit(client)
    submit(client, category="exposed_wiring")
    summary = {t["id"]: t for t in client.get("/transformers").json()}
    assert summary["T1"]["open_reports"] == 2
    assert summary["T2"]["open_reports"] == 0
    detail = client.get("/transformers/T1").json()
    assert {r["category"] for r in detail["community_reports"]} == {"cable_theft", "exposed_wiring"}


def test_patrol_can_dispatch_and_resolve(client, patrol_code):
    report_id = submit(client).json()["id"]
    headers = {"X-Patrol-Code": patrol_code}

    dispatched = client.patch(f"/reports/{report_id.lower()}", json={"status": "dispatched"}, headers=headers)
    assert dispatched.status_code == 200
    assert dispatched.json()["status"] == "dispatched"
    assert dispatched.json()["updated_at"]

    client.patch(f"/reports/{report_id}", json={"status": "resolved"}, headers=headers)
    assert client.get("/reports").json() == []
    assert len(client.get("/reports?include_resolved=true").json()) == 1
    assert client.get("/transformers/T1").json()["open_reports"] == 0


def test_status_update_needs_the_right_code(client, patrol_code):
    report_id = submit(client).json()["id"]
    body = {"status": "resolved"}
    assert client.patch(f"/reports/{report_id}", json=body).status_code == 403
    wrong = {"X-Patrol-Code": "guess"}
    assert client.patch(f"/reports/{report_id}", json=body, headers=wrong).status_code == 403
    assert client.get("/reports").json()[0]["status"] == "new"


def test_status_updates_disabled_without_a_code(client, monkeypatch):
    monkeypatch.setattr(settings, "patrol_code", "")
    report_id = submit(client).json()["id"]
    response = client.patch(
        f"/reports/{report_id}", json={"status": "resolved"}, headers={"X-Patrol-Code": ""}
    )
    assert response.status_code == 503


def test_unknown_report_is_404(client, patrol_code):
    response = client.patch(
        "/reports/NOPE42", json={"status": "resolved"}, headers={"X-Patrol-Code": patrol_code}
    )
    assert response.status_code == 404
