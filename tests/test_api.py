"""Tests para la API REST FastAPI."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from dashboard.api import DB_PATH, app


@pytest.fixture(autouse=True)
def _clean_db(tmp_path: Path) -> None:
    """Crea una BD temporal para cada test."""
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE raw_data (id INTEGER, title TEXT, scraped_at TEXT, source_domain TEXT, source_url TEXT)")
    conn.execute(
        "CREATE TABLE processed_data (id INTEGER, title TEXT, scraped_at TEXT, source_domain TEXT, source_url TEXT)",
    )
    conn.execute(
        "INSERT INTO raw_data VALUES (1, 'Test', '2026-07-01T00:00:00', 'example.com', 'https://example.com')",
    )
    conn.execute(
        "INSERT INTO raw_data VALUES (2, 'Test 2', '2026-07-02T00:00:00', 'test.org', 'https://test.org')",
    )
    conn.execute(
        "INSERT INTO processed_data VALUES (1, 'Test', '2026-07-01T00:00:00', 'example.com', 'https://example.com')",
    )
    conn.commit()
    conn.close()

    # Sobrescribir DB_PATH global para este test
    global _original_db
    _original_db = str(DB_PATH)
    app.dependency_overrides = {}
    import dashboard.api as api_mod

    api_mod.DB_PATH = db


@pytest.fixture
def client() -> Any:
    with TestClient(app) as c:
        yield c


def test_health_ok(client: Any) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "db" in data
    assert data["db"]["exists"] is True
    assert data["db"]["size_bytes"] > 0


def test_health_no_db(client: Any) -> None:
    import dashboard.api as api_mod

    api_mod.DB_PATH = Path("/nonexistent/test.db")
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["db"]["exists"] is False


def test_metrics_endpoint(client: Any) -> None:
    resp = client.get("/metrics")
    assert resp.status_code == 200
    text = resp.text
    assert "etl_health_status" in text
    assert "etl_raw_data_total" in text
    assert "etl_db_size_bytes" in text


def test_data_endpoint(client: Any) -> None:
    resp = client.get("/data?table=raw_data")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["rows"]) == 2
    assert data["rows"][0]["title"] == "Test"


def test_data_pagination(client: Any) -> None:
    resp = client.get("/data?table=raw_data&limit=1&offset=1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["rows"]) == 1
    assert data["rows"][0]["title"] == "Test 2"


def test_stats_endpoint(client: Any) -> None:
    resp = client.get("/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data or "rows" in data or isinstance(data, dict)
