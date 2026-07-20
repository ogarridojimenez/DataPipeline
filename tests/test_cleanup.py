"""Tests para etl.cleanup — data retention."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

from etl.cleanup import cleanup_db


def test_cleanup_removes_old_data(tmp_path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE raw_data (id INTEGER, scraped_at TEXT)")
    conn.execute("CREATE TABLE processed_data (id INTEGER, scraped_at TEXT)")
    conn.execute("INSERT INTO raw_data VALUES (1, '2020-01-01T00:00:00')")
    conn.execute("INSERT INTO raw_data VALUES (2, '2026-07-01T00:00:00')")
    conn.execute("INSERT INTO processed_data VALUES (1, '2020-01-01T00:00:00')")
    conn.execute("INSERT INTO processed_data VALUES (2, '2026-07-01T00:00:00')")
    conn.commit()
    conn.close()

    removed = cleanup_db(str(db), days=30)
    assert removed == {"raw_data": 1, "processed_data": 1}
    conn2 = sqlite3.connect(str(db))
    remaining = conn2.execute("SELECT COUNT(*) FROM raw_data").fetchone()[0]
    assert remaining == 1
    conn2.close()


def test_cleanup_dry_run_does_not_delete(tmp_path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE raw_data (id INTEGER, scraped_at TEXT)")
    conn.execute("CREATE TABLE processed_data (id INTEGER, scraped_at TEXT)")
    conn.execute("INSERT INTO raw_data VALUES (1, '2020-01-01T00:00:00')")
    conn.execute("INSERT INTO processed_data VALUES (1, '2020-01-01T00:00:00')")
    conn.commit()
    conn.close()

    removed = cleanup_db(str(db), days=30, dry_run=True)
    assert removed == {"raw_data": 1, "processed_data": 1}
    conn2 = sqlite3.connect(str(db))
    remaining = conn2.execute("SELECT COUNT(*) FROM raw_data").fetchone()[0]
    assert remaining == 1  # still there
    conn2.close()


def test_cleanup_no_old_data(tmp_path):
    """Registros recientes (1 hora atrás) con days=1 no deben eliminarse."""
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE raw_data (id INTEGER, scraped_at TEXT)")
    conn.execute("CREATE TABLE processed_data (id INTEGER, scraped_at TEXT)")
    recent = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    conn.execute("INSERT INTO raw_data VALUES (1, ?)", (recent,))
    conn.execute("INSERT INTO processed_data VALUES (1, ?)", (recent,))
    conn.commit()
    conn.close()

    removed = cleanup_db(str(db), days=1)
    assert removed == {"raw_data": 0, "processed_data": 0}
