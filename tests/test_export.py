"""Tests para etl.export — exportación incremental."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from etl.config import ProcessConfig
from etl.export import load_processed, load_processed_df, run_export


def test_load_processed_incremental(tmp_path: Path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE processed_data (id INTEGER, title TEXT, scraped_at TEXT, source_domain TEXT, source_url TEXT)",
    )
    conn.execute("INSERT INTO processed_data VALUES (1, 'A', '2026-01-01T00:00:00', 'a.com', 'https://a.com')")
    conn.execute("INSERT INTO processed_data VALUES (2, 'B', '2026-07-01T00:00:00', 'b.com', 'https://b.com')")
    conn.execute("INSERT INTO processed_data VALUES (3, 'C', '2026-07-20T00:00:00', 'c.com', 'https://c.com')")
    conn.commit()
    conn.close()

    _cols, rows = load_processed(db, since="2026-07-01")
    assert len(rows) == 2  # B and C

    _cols2, rows2 = load_processed(db, since="2026-12-01")
    assert len(rows2) == 0  # nothing newer

    _cols3, rows3 = load_processed(db, since=None)
    assert len(rows3) == 3  # all


def test_run_export_with_since(tmp_path: Path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE processed_data (id INTEGER, title TEXT, scraped_at TEXT, source_domain TEXT, source_url TEXT)",
    )
    conn.execute("INSERT INTO processed_data VALUES (1, 'Old', '2020-01-01T00:00:00', 'x.com', 'https://x.com')")
    conn.execute("INSERT INTO processed_data VALUES (2, 'New', '2026-07-20T00:00:00', 'y.com', 'https://y.com')")
    conn.commit()
    conn.close()

    out = tmp_path / "out"
    out.mkdir()
    config = ProcessConfig(output_dir=out)

    run_export(db_path=db, config=config, since="2026-01-01")
    csv_file = out / "datapipeline_export.csv"
    assert csv_file.exists()
    df = pd.read_csv(csv_file)
    assert len(df) == 1
    assert df.iloc[0]["title"] == "New"


def test_load_processed_df_empty(tmp_path: Path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE processed_data (id INTEGER, title TEXT, scraped_at TEXT, source_domain TEXT, source_url TEXT)",
    )
    conn.commit()
    conn.close()

    df = load_processed_df(db)
    assert df.empty
