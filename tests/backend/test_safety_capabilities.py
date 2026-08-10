from __future__ import annotations

from fastapi.testclient import TestClient


def test_local_ai_gracefully_disables(client: TestClient, auth: dict[str, str]):
    status = client.get("/api/ai/status")
    assert status.status_code == 200
    assert status.json()["available"] is False
    query = client.post("/api/ai/query", headers=auth, json={"question": "What should I take?", "profile_id": None})
    assert query.status_code == 200
    assert "could not find supporting" in query.json()["answer"].lower()


def test_ocr_failure_never_changes_medical_records(client: TestClient, auth: dict[str, str], profile_id: str):
    # No document means extraction cannot silently create a prescription.
    result = client.post("/api/documents/missing/extract", headers=auth)
    assert result.status_code == 404
    assert client.get("/api/prescriptions").json() == []


def test_security_headers_and_api_schema(client: TestClient):
    response = client.get("/api/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "object-src 'none'" in response.headers["content-security-policy"]
    schema = client.get("/api/openapi.json")
    assert schema.status_code == 200
    assert schema.json()["info"]["version"] == "0.1.0"
