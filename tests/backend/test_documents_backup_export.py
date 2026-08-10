from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image


def png_bytes() -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (80, 100), "white").save(stream, format="PNG")
    return stream.getvalue()


def upload_document(client: TestClient, auth: dict[str, str], profile_id: str):
    return client.post("/api/documents", headers=auth, data={"profile_id": profile_id, "category": "prescription", "document_date": "2026-08-10", "title": "Synthetic prescription"}, files={"file": ("fictional.png", png_bytes(), "image/png")})


def test_document_original_preserved_and_duplicate_detected(client: TestClient, auth: dict[str, str], profile_id: str, vault_data_dir: Path):
    first = upload_document(client, auth, profile_id)
    assert first.status_code == 201, first.text
    assert first.json()["duplicate"] is False
    item = first.json()["document"]
    stored = vault_data_dir / item["relative_path"]
    assert stored.read_bytes() == png_bytes()
    second = upload_document(client, auth, profile_id)
    assert second.status_code == 201
    assert second.json()["duplicate"] is True
    assert second.json()["document"]["id"] == item["id"]


def test_file_signature_not_declared_mime_controls_acceptance(client: TestClient, auth: dict[str, str], profile_id: str):
    response = client.post("/api/documents", headers=auth, data={"profile_id": profile_id, "category": "other"}, files={"file": ("fake.pdf", b"not a real pdf", "application/pdf")})
    assert response.status_code == 415


def _create_backup(client: TestClient, auth: dict[str, str], password: str = "backup password long enough") -> Path:
    result = client.post("/api/backups/create", headers=auth, json={"password": password, "kind": "manual"})
    assert result.status_code == 200, result.text
    destinations = result.json()["destination_results"]
    return Path(destinations[0]["path"])


def test_backup_encrypts_verifies_and_rejects_wrong_password(client: TestClient, auth: dict[str, str], profile_id: str):
    upload_document(client, auth, profile_id)
    backup = _create_backup(client, auth)
    assert backup.read_bytes()[:8] == b"HVAULT01"
    assert not backup.read_bytes().startswith(b"PK")
    wrong = client.post("/api/backups/verify", headers=auth, json={"path": str(backup), "password": "wrong"})
    assert wrong.status_code == 401
    verified = client.post("/api/backups/verify", headers=auth, json={"path": str(backup), "password": "backup password long enough"})
    assert verified.status_code == 200, verified.text
    assert verified.json()["manifest"]["profile_count"] == 1


def test_test_restore_opens_database_and_checks_documents(client: TestClient, auth: dict[str, str], profile_id: str):
    upload_document(client, auth, profile_id)
    backup = _create_backup(client, auth)
    tested = client.post("/api/backups/test-restore", headers=auth, json={"path": str(backup), "password": "backup password long enough"})
    assert tested.status_code == 200, tested.text
    assert tested.json()["test_restore"] == "passed"
    assert tested.json()["profile_count"] == 1


def test_full_restore_reverts_database_and_recovers_missing_original(client: TestClient, auth: dict[str, str], profile_id: str, vault_data_dir: Path):
    first_note = client.post("/api/notes", headers=auth, json={"profile_id": profile_id, "visit_id": None, "prescribed_medication_id": None, "occurred_at": "2026-08-10T08:00:00Z", "title": "Before backup", "content": "Synthetic retained record"})
    document = upload_document(client, auth, profile_id).json()["document"]
    backup = _create_backup(client, auth)
    client.post("/api/notes", headers=auth, json={"profile_id": profile_id, "visit_id": None, "prescribed_medication_id": None, "occurred_at": "2026-08-10T09:00:00Z", "title": "After backup", "content": "Synthetic record that should be rolled back"})
    original = vault_data_dir / document["relative_path"]
    original.unlink()
    assert not original.exists()
    restored = client.post("/api/backups/restore", headers=auth, json={"path": str(backup), "password": "backup password long enough"})
    assert restored.status_code == 200, restored.text
    assert restored.json()["emergency_backup"].endswith(".hvault")
    titles = {item["title"] for item in client.get("/api/notes").json()}
    assert "Before backup" in titles
    assert "After backup" not in titles
    assert original.read_bytes() == png_bytes()


def test_corrupt_backup_is_detected(client: TestClient, auth: dict[str, str], tmp_path: Path):
    corrupt = tmp_path / "corrupt.hvault"
    corrupt.write_bytes(b"HVAULT01" + b"\x01" + b"x" * 64)
    result = client.post("/api/backups/verify", headers=auth, json={"path": str(corrupt), "password": "backup password long enough"})
    assert result.status_code in {400, 401}


def test_export_contains_portable_json_csv_markdown_manifest_and_originals(client: TestClient, auth: dict[str, str], profile_id: str):
    upload_document(client, auth, profile_id)
    created = client.post("/api/exports", headers=auth)
    assert created.status_code == 200
    download = client.get(created.json()["download_url"])
    assert download.status_code == 200
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        names = set(archive.namelist())
        assert "manifest.json" in names
        assert "profiles/profiles.json" in names
        assert "profiles/profiles.csv" in names
        assert "profiles/profiles.md" in names
        assert "DATA_FORMAT.md" in names
        assert any(name.startswith("attachments/documents/originals/") for name in names)


def test_calendar_export_is_standard_ics(client: TestClient, auth: dict[str, str], profile_id: str):
    appointment = client.post("/api/appointments", headers=auth, json={"profile_id": profile_id, "provider_id": None, "starts_at": "2026-08-20T10:30:00+05:30", "purpose": "Synthetic follow-up", "location": "Example Clinic", "preparation_notes": "Bring report", "documents_to_carry": "Report", "reminder_minutes": 1440, "status": "scheduled", "post_visit_notes": None})
    assert appointment.status_code == 201
    reminders = client.get("/api/reminders", params={"profile_id": profile_id}).json()
    assert any(item["appointment_id"] == appointment.json()["id"] for item in reminders)
    calendar = client.get("/api/appointments.ics")
    assert calendar.status_code == 200
    assert "BEGIN:VCALENDAR" in calendar.text
    assert "Synthetic follow-up" in calendar.text
