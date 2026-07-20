"""Tests para dashboard.queries — consultas SQL."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from dashboard.queries import get_column_names, get_records, get_stats


def test_get_stats(tmp_path: Path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE processed_data (id INTEGER, title TEXT, scraped_at TEXT, source_domain TEXT, source_url TEXT)",
    )
    conn.execute("INSERT INTO processed_data VALUES (1, 'A', '2026-07-01', 'x.com', 'https://x.com')")
    conn.execute("INSERT INTO processed_data VALUES (2, 'B', '2026-07-02', 'y.com', 'https://y.com')")
    conn.commit()
    conn.close()

    stats = get_stats(db)
    assert stats["total_records"] == 2
    assert stats["unique_domains"] == 2
    assert stats["unique_urls"] == 2


def test_get_stats_empty(tmp_path: Path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE processed_data (id INTEGER, title TEXT, scraped_at TEXT, source_domain TEXT, source_url TEXT)",
    )
    conn.commit()
    conn.close()

    stats = get_stats(db)
    assert stats["total_records"] == 0


def test_get_records_paginated(tmp_path: Path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE processed_data (id INTEGER, title TEXT, scraped_at TEXT, source_domain TEXT, source_url TEXT)",
    )
    for i in range(10):
        conn.execute(
            "INSERT INTO processed_data VALUES (?, ?, '2026-07-01', 'x.com', 'https://x.com')",
            (i, f"Row {i}"),
        )
    conn.commit()
    conn.close()

    data = get_records(db, limit=3, offset=0)
    assert len(data) == 3
    assert data[0]["id"] == 9
    assert data[-1]["id"] == 7

    data2 = get_records(db, limit=3, offset=3)
    assert len(data2) == 3
    assert data2[0]["id"] == 6


def test_get_records_empty(tmp_path: Path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE processed_data (id INTEGER)")
    conn.commit()
    conn.close()

    data = get_records(db)
    assert data == []


def test_get_column_names(tmp_path: Path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE processed_data (id INTEGER, title TEXT, scraped_at TEXT, source_domain TEXT, source_url TEXT, price REAL)",
    )
    conn.commit()
    conn.close()

    cols = get_column_names(db)
    assert "price" in cols
    assert "title" in cols
    assert "id" not in cols  # metadata excluded
