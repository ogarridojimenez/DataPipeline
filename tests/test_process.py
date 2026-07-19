"""Tests para etl.process — unit tests con stdlib."""

import json
import sqlite3
from pathlib import Path

import pytest

from etl.process import load_raw_data, clean_data, save_processed, _try_numeric
from etl.config import ProcessConfig


@pytest.fixture
def sample_db(tmp_path):
    """Crea una DB SQLite temporal con datos de prueba."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE raw_data (
            id INTEGER PRIMARY KEY,
            source_url TEXT,
            source_domain TEXT,
            data TEXT,
            scraped_at TIMESTAMP
        )
    """)

    data_items = [
        [{"title": "A", "price": "100"}, {"title": "B", "price": "200"}, {"title": "A", "price": "100"}],
        [{"title": "C", "price": "50"}],
    ]
    for items in data_items:
        cursor.execute(
            "INSERT INTO raw_data (source_url, source_domain, data) VALUES (?, ?, ?)",
            ("http://test.com", "test.com", json.dumps(items)),
        )

    conn.commit()
    conn.close()
    return db_path


class TestLoadRawData:
    def test_loads_and_expands_json(self, sample_db):
        records = load_raw_data(sample_db)
        assert len(records) == 4  # 3 + 1 items
        assert "title" in records[0]
        assert "price" in records[0]

    def test_empty_db(self, tmp_path):
        db = tmp_path / "empty.db"
        conn = sqlite3.connect(str(db))
        conn.execute("""CREATE TABLE raw_data (id INTEGER, source_url TEXT, source_domain TEXT, data TEXT, scraped_at TIMESTAMP)""")
        conn.commit()
        conn.close()
        records = load_raw_data(db)
        assert records == []


class TestCleanData:
    def test_removes_duplicates(self, sample_db):
        records = load_raw_data(sample_db)
        config = ProcessConfig(fill_null_strategy="drop")
        cleaned = clean_data(records, config)
        # Duplicado exacto "A"/"100" eliminado
        assert len(cleaned) == 3

    def test_fill_nulls_strategy(self, sample_db):
        records = load_raw_data(sample_db)
        records[0]["title"] = ""
        config = ProcessConfig(fill_null_strategy="fill")
        cleaned = clean_data(records, config)
        assert cleaned[0]["title"] == ""

    def test_drop_nulls_strategy(self, sample_db):
        records = load_raw_data(sample_db)
        records[0]["title"] = ""
        config = ProcessConfig(fill_null_strategy="drop")
        cleaned = clean_data(records, config)
        assert len(cleaned) == 3  # 1 dropped

    def test_outlier_marking(self, tmp_path):
        db = tmp_path / "outlier.db"
        conn = sqlite3.connect(str(db))
        conn.execute("""CREATE TABLE raw_data (id INTEGER, source_url TEXT, source_domain TEXT, data TEXT, scraped_at TIMESTAMP)""")
        items = [{"val": str(v)} for v in [10, 12, 11, 13, 10, 100]]
        conn.execute("INSERT INTO raw_data (source_url, source_domain, data) VALUES (?, ?, ?)",
                     ("http://t.com", "t.com", json.dumps(items)))
        conn.commit()
        conn.close()

        records = load_raw_data(db)
        config = ProcessConfig(outlier_std_threshold=2.0)
        cleaned = clean_data(records, config)
        outliers = [r for r in cleaned if r.get("val_is_outlier")]
        assert len(outliers) >= 1  # 100 es outlier

    def test_try_numeric(self):
        assert _try_numeric("42") == 42.0
        assert _try_numeric("3.14") == 3.14
        assert _try_numeric("hello") == "hello"
        assert _try_numeric("") == ""


class TestSaveProcessed:
    def test_saves_to_sqlite(self, sample_db):
        records = load_raw_data(sample_db)
        save_processed(records, sample_db)

        conn = sqlite3.connect(str(sample_db))
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM processed_data")
        rows = cursor.fetchall()
        conn.close()
        assert len(rows) == 4
