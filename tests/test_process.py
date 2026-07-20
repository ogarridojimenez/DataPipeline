"""Tests para etl.process — data loading, cleaning, and transforms."""

import json
import sqlite3

import pytest

from etl.config import ProcessConfig
from etl.process import clean_data, load_raw_data, save_processed


@pytest.fixture
def sample_db(tmp_path):
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
        df = load_raw_data(sample_db)
        assert len(df) == 4
        assert "title" in df.columns
        assert "price" in df.columns

    def test_empty_db(self, tmp_path):
        db = tmp_path / "empty.db"
        conn = sqlite3.connect(str(db))
        conn.execute(
            """CREATE TABLE raw_data (id INTEGER, source_url TEXT, source_domain TEXT, data TEXT, scraped_at TIMESTAMP)"""
        )
        conn.commit()
        conn.close()
        df = load_raw_data(db)
        assert df.empty


class TestCleanData:
    def test_removes_duplicates(self, sample_db):
        df = load_raw_data(sample_db)
        config = ProcessConfig(fill_null_strategy="drop")
        cleaned = clean_data(df, config)
        assert len(cleaned) == 3

    def test_fill_nulls_strategy(self, sample_db):
        df = load_raw_data(sample_db)
        df.loc[0, "title"] = ""
        config = ProcessConfig(fill_null_strategy="fill")
        cleaned = clean_data(df, config)
        assert cleaned.iloc[0]["title"] == ""

    def test_drop_nulls_strategy(self, sample_db):
        df = load_raw_data(sample_db)
        df.loc[0, "title"] = None
        config = ProcessConfig(fill_null_strategy="drop")
        cleaned = clean_data(df, config)
        assert len(cleaned) <= 4


class TestSaveProcessed:
    def test_saves_to_sqlite(self, sample_db):
        df = load_raw_data(sample_db)
        save_processed(df, sample_db)
        conn = sqlite3.connect(str(sample_db))
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM processed_data")
        rows = cursor.fetchall()
        conn.close()
        assert len(rows) == 4
