from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient


def test_first_run_requires_localhost_and_creates_locked_session(client: TestClient):
    status = client.get("/api/status")
    assert status.status_code == 200
    assert status.json()["configured"] is False
    created = client.post("/api/setup", json={"password": "long local password", "profile_name": "Alex Example"})
    assert created.status_code == 201
    assert created.json()["profile"]["name"] == "Alex Example"
    assert client.get("/api/auth/me").status_code == 200
    duplicate = client.post("/api/setup", json={"password": "another password", "profile_name": "Sam Example"})
    assert duplicate.status_code == 409


def test_password_login_rejects_wrong_password(client: TestClient, auth: dict[str, str]):
    assert client.post("/api/auth/logout", headers=auth).status_code == 200
    wrong = client.post("/api/auth/login", json={"password": "definitely wrong"})
    assert wrong.status_code == 401
    right = client.post("/api/auth/login", json={"password": "correct horse battery"})
    assert right.status_code == 200
    assert right.json()["csrf_token"]


def test_csrf_blocks_mutation(client: TestClient, auth: dict[str, str]):
    denied = client.post("/api/notes", json={"profile_id": "missing", "content": "No token"})
    assert denied.status_code == 403


def test_crud_audit_search_and_soft_delete(client: TestClient, auth: dict[str, str], profile_id: str):
    provider = client.post("/api/providers", headers=auth, json={"name": "Dr Fiction", "specialty": "Orthopedics", "hospital": "Example Clinic", "phone": None, "address": None, "notes": None})
    assert provider.status_code == 201
    visit = client.post("/api/visits", headers=auth, json={
        "profile_id": profile_id,
        "provider_id": provider.json()["id"],
        "visit_date": datetime.now(timezone.utc).isoformat(),
        "reason": "Left knee pain after fictional fall",
        "symptoms": "Knee tenderness",
        "clinical_impression": "Sprain as written",
        "diagnosis_text": "Knee sprain",
        "follow_up_date": None,
        "summary": "Synthetic fixture visit",
        "notes": None,
        "appointment_id": None,
    })
    assert visit.status_code == 201, visit.text
    results = client.get("/api/search", params={"q": "knee pain", "profile_id": profile_id})
    assert results.status_code == 200
    assert any(row["entity_id"] == visit.json()["id"] for row in results.json())
    audit = client.get("/api/audit", params={"entity_id": visit.json()["id"]}).json()
    assert audit and audit[0]["operation"] == "create"
    deleted = client.delete(f"/api/visits/{visit.json()['id']}", headers=auth)
    assert deleted.status_code == 204
    assert all(row["id"] != visit.json()["id"] for row in client.get("/api/visits").json())
    restored = client.post(f"/api/visits/{visit.json()['id']}/restore", headers=auth)
    assert restored.status_code == 200


def test_manual_medication_requires_name_and_can_record_dose(client: TestClient, auth: dict[str, str], profile_id: str):
    invalid = client.post("/api/medications", headers=auth, json={"generic_name": None, "brand_name": None, "strength": None, "form": None, "manufacturer": None, "notes": None})
    assert invalid.status_code == 422
    medication = client.post("/api/medications", headers=auth, json={"generic_name": "Examplemol", "brand_name": "FictionTab", "strength": "10 mg", "form": "tablet", "manufacturer": None, "notes": None})
    today = datetime.now(timezone.utc).date()
    prescribed = client.post("/api/prescribed-medications", headers=auth, json={"prescription_id": None, "profile_id": profile_id, "medication_id": medication.json()["id"], "dosage": "1 tablet", "frequency": "once daily", "timing": "08:00", "duration": "5 days", "start_date": (today - timedelta(days=1)).isoformat(), "end_date": (today + timedelta(days=3)).isoformat(), "food_relation": "after food", "instructions": "Synthetic instruction", "as_needed": False, "verification_status": "verified", "tracking_status": "active", "schedule": {"times": ["08:00"]}})
    assert prescribed.status_code == 201, prescribed.text
    dose = client.post("/api/doses", headers=auth, json={"prescribed_medication_id": prescribed.json()["id"], "scheduled_at": datetime.now(timezone.utc).isoformat(), "status": "taken", "note": None})
    assert dose.status_code == 201
    reminders = client.get("/api/reminders", params={"profile_id": profile_id}).json()
    medicine_reminder = next(item for item in reminders if item["prescribed_medication_id"] == prescribed.json()["id"])
    assert medicine_reminder["kind"] == "medication"
    completed = client.post(f"/api/reminders/{medicine_reminder['id']}/complete", headers=auth)
    assert completed.status_code == 200
    assert completed.json()["next"]["status"] == "pending"


def test_timeline_and_dashboard_combine_records(client: TestClient, auth: dict[str, str], profile_id: str):
    note = client.post("/api/notes", headers=auth, json={"profile_id": profile_id, "visit_id": None, "prescribed_medication_id": None, "occurred_at": datetime.now(timezone.utc).isoformat(), "title": "Synthetic fever note", "content": "Fever started today in fictional fixture."})
    assert note.status_code == 201
    timeline = client.get(f"/api/timeline/{profile_id}").json()
    assert any(item["kind"] == "note" for item in timeline)
    dashboard = client.get("/api/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["profiles"][0]["name"] == "Alex Example"
