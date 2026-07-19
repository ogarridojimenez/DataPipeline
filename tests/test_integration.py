"""Tests de integración end-to-end: scrape → process → export."""

import json
import sqlite3
from pathlib import Path

import pytest

from etl.process import load_raw_data, clean_data, save_processed
from etl.export import run_export
from etl.config import ProcessConfig


def _create_test_db(db_path: Path) -> None:
    """Popula DB con datos simulando output de scrape."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_url TEXT,
            source_domain TEXT,
            data TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    items = [
        {"product": "Laptop", "price": "999", "category": "electronics"},
        {"product": "Mouse", "price": "25", "category": "electronics"},
        {"product": "Laptop", "price": "999", "category": "electronics"},  # dup
        {"product": "Book", "price": "15", "category": "books"},
        {"product": "", "price": "30", "category": "misc"},  # empty
    ]
    conn.execute(
        "INSERT INTO raw_data (source_url, source_domain, data) VALUES (?, ?, ?)",
        ("http://test.com/products", "test.com", json.dumps(items)),
    )
    conn.commit()
    conn.close()


class TestEndToEnd:
    def test_full_pipeline(self, tmp_path):
        db_path = tmp_path / "pipeline.db"
        output_dir = tmp_path / "output"

        # 1. Simular scrape
        _create_test_db(db_path)

        # 2. Process
        config = ProcessConfig(fill_null_strategy="drop", output_dir=output_dir)
        records = load_raw_data(db_path)
        assert len(records) == 5

        cleaned = clean_data(records, config)
        assert len(cleaned) == 4  # 1 dup removed, 1 empty dropped
        save_processed(cleaned, db_path)

        # 3. Export
        run_export(db_path, config, fmt="both")

        assert (output_dir / "datapipeline_export.csv").exists()
        assert (output_dir / "datapipeline_export.json").exists()

        # Verificar CSV
        import csv
        with open(output_dir / "datapipeline_export.csv") as f:
            reader = csv.DictReader(f)
            csv_rows = list(reader)
        assert len(csv_rows) == 4

        # Verificar JSON
        with open(output_dir / "datapipeline_export.json") as f:
            json_data = json.load(f)
        assert len(json_data) == 4
