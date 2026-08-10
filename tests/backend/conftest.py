from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ["HEALTHVAULT_DATA_DIR"] = tempfile.mkdtemp(prefix="healthvault-tests-")
os.environ["HEALTHVAULT_OLLAMA_URL"] = "http://127.0.0.1:9"

import pytest
from fastapi.testclient import TestClient

from backend.database import engine
from backend.main import app
from backend.models import Base


@pytest.fixture(autouse=True)
def clean_database():
    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
        conn.exec_driver_sql("DROP TABLE IF EXISTS search_index")
        Base.metadata.drop_all(conn)
        Base.metadata.create_all(conn)
        conn.exec_driver_sql("CREATE VIRTUAL TABLE search_index USING fts5(entity_type UNINDEXED, entity_id UNINDEXED, profile_id UNINDEXED, title, content, event_date UNINDEXED, tokenize='unicode61 remove_diacritics 2')")
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
    yield


@pytest.fixture
def client():
    with TestClient(app, client=("testclient", 50000)) as test_client:
        yield test_client


@pytest.fixture
def auth(client: TestClient) -> dict[str, str]:
    response = client.post("/api/setup", json={"password": "correct horse battery", "profile_name": "Alex Example"})
    assert response.status_code == 201, response.text
    body = response.json()
    return {"X-CSRF-Token": body["csrf_token"]}


@pytest.fixture
def profile_id(client: TestClient, auth: dict[str, str]) -> str:
    return client.get("/api/profiles").json()[0]["id"]


@pytest.fixture
def vault_data_dir() -> Path:
    return Path(os.environ["HEALTHVAULT_DATA_DIR"])
