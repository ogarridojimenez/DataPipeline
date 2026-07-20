"""Tests adicionales para edge cases del pipeline."""

from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from etl.config import ProcessConfig
from etl.process import (
    compute_summary,
    expand_json_records,
    group_by_domain,
    pipeline_pipe,
    run_process,
    save_processed,
)
from etl.scrape import extract_data

# ── Process edge cases ──


def test_expand_json_empty():
    df = expand_json_records(pd.DataFrame(columns=["data"]))
    assert df.empty


def test_expand_json_single_col():
    df = pd.DataFrame({"data": ['{"a":1}']})
    result = expand_json_records(df)
    assert "a" in result.columns
    assert result.iloc[0]["a"] == 1


def test_group_by_domain_no_numeric():
    df = pd.DataFrame(
        {
            "_source_domain": ["x.com", "y.com"],
            "title": ["A", "B"],
        }
    )
    result = group_by_domain(df)
    assert "count" in result.columns
    assert len(result) == 2


def test_group_by_domain_empty():
    assert group_by_domain(pd.DataFrame()).empty


def test_pipeline_pipe_normalize_same_value():
    df = pd.DataFrame({"x": [5, 5, 5]})
    result = pipeline_pipe(df, [{"type": "normalize", "params": {"column": "x", "name": "x_norm"}}])
    assert (result["x_norm"] == 0).all()


def test_pipeline_pipe_zscore():
    df = pd.DataFrame({"x": [1, 2, 3]})
    result = pipeline_pipe(df, [{"type": "normalize", "params": {"column": "x", "method": "zscore"}}])
    assert abs(result["x_norm"].mean()) < 0.01


def test_pipeline_pipe_zscore_same_value():
    df = pd.DataFrame({"x": [5, 5, 5]})
    result = pipeline_pipe(df, [{"type": "normalize", "params": {"column": "x", "method": "zscore"}}])
    assert (result["x_norm"] == 0).all()


def test_pipeline_pipe_add_rank():
    df = pd.DataFrame({"x": [1, 3, 2]})
    result = pipeline_pipe(df, [{"type": "add_rank", "params": {"column": "x"}}])
    assert list(result["rank"]) == [1.0, 3.0, 2.0]


def test_pipeline_pipe_filter_ops():
    df = pd.DataFrame({"x": [1, 2, 3, 4, 5]})
    for op in ("eq", "gt", "gte", "lt", "lte", "ne", "contains"):
        params = {"column": "x", "op": op, "value": 3}
        if op == "contains":
            params["value"] = "3"
        result = pipeline_pipe(df, [{"type": "filter", "params": params}])
        assert len(result) > 0


def test_save_processed_empty(tmp_path):
    df = pd.DataFrame(columns=["title", "_source_domain"])
    db = tmp_path / "test.db"
    save_processed(df, db)
    conn = sqlite3.connect(str(db))
    rows = conn.execute("SELECT COUNT(*) FROM processed_data").fetchone()[0]
    conn.close()
    assert rows == 0


def test_run_process_empty_db(tmp_path, caplog):
    import logging

    caplog.set_level(logging.WARNING)
    db = str(tmp_path / "empty.db")
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE raw_data (id INTEGER, data TEXT)")
    conn.commit()
    conn.close()
    run_process(db, ProcessConfig(), verbose=False)
    assert "No hay datos" in caplog.text


def test_compute_summary_empty():
    assert compute_summary(pd.DataFrame()) == {}


def test_compute_summary_meta_only():
    df = pd.DataFrame({"_meta_key": ["a"]})
    result = compute_summary(df)
    assert result.get("numeric_columns", 0) == 0


# ── Scrape edge cases ──


def test_extract_data_nested_selector():
    html = "<div><p class='x'>Hello</p><p class='x'>World</p></div>"
    result = extract_data(html, ["p.x"], url="http://test.com", domain="test.com")
    assert len(result) >= 1
    assert result[0]["x"] in ("Hello", "World")


# ── Config edge cases ──


def test_config_validate_db_project_root(tmp_path):
    from etl.config import validate_db_path

    db = tmp_path / "sub" / "test.db"
    db.parent.mkdir()
    db.touch()
    result = validate_db_path(str(db), project_root=tmp_path)
    assert result is not None


def test_config_validate_db_outside_project(tmp_path):
    from etl.config import validate_db_path

    # Create a clearly non-overlapping root
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside.db"
    outside.touch()
    with pytest.raises(ValueError, match="fuera del proyecto"):
        validate_db_path(str(outside), project_root=root)


# ── Export edge cases ──


def test_export_fallback_raw(tmp_path):
    """Export se cae a raw_data si processed_data no existe."""
    from etl.export import load_processed

    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE raw_data (id INTEGER, scraped_at TEXT)")
    conn.execute("INSERT INTO raw_data VALUES (1, '2026-07-01')")
    conn.commit()
    conn.close()
    cols, rows = load_processed(db)
    assert len(rows) == 1
    assert "id" in cols


# ── Queries edge cases ──


def test_queries_top_items(tmp_path):
    from dashboard.queries import get_top_items

    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE processed_data (id INTEGER, title TEXT)")
    conn.execute("INSERT INTO processed_data VALUES (1, 'A')")
    conn.execute("INSERT INTO processed_data VALUES (2, 'A')")
    conn.execute("INSERT INTO processed_data VALUES (3, 'B')")
    conn.commit()
    conn.close()
    items = get_top_items(db, n=2, column="title")
    assert len(items) == 2
    assert items[0]["cnt"] == 2  # A appears twice


def test_queries_top_items_bad_column(tmp_path):
    from dashboard.queries import get_top_items

    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE processed_data (id INTEGER)")
    conn.commit()
    conn.close()
    items = get_top_items(db, column="no_such_col")
    assert items == []


def test_queries_time_series(tmp_path):
    from dashboard.queries import get_time_series

    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE processed_data (id INTEGER, scraped_at TEXT)")
    conn.execute("INSERT INTO processed_data VALUES (1, '2026-07-01')")
    conn.execute("INSERT INTO processed_data VALUES (2, '2026-07-01')")
    conn.execute("INSERT INTO processed_data VALUES (3, '2026-07-02')")
    conn.commit()
    conn.close()
    ts = get_time_series(db)
    assert len(ts) == 2
    assert ts[0]["cnt"] == 2


def test_queries_domain_breakdown(tmp_path):
    from dashboard.queries import get_domain_breakdown

    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE processed_data (id INTEGER, source_domain TEXT)")
    conn.execute("INSERT INTO processed_data VALUES (1, 'x.com')")
    conn.execute("INSERT INTO processed_data VALUES (2, 'y.com')")
    conn.execute("INSERT INTO processed_data VALUES (3, 'x.com')")
    conn.commit()
    conn.close()
    dbd = get_domain_breakdown(db)
    assert len(dbd) == 2
    assert dbd[0]["cnt"] == 2


def test_queries_get_records_filtered(tmp_path):
    from dashboard.queries import get_records

    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE processed_data (id INTEGER, source_domain TEXT)")
    conn.execute("INSERT INTO processed_data VALUES (1, 'x.com')")
    conn.execute("INSERT INTO processed_data VALUES (2, 'y.com')")
    conn.commit()
    conn.close()
    records = get_records(db, domain="x.com")
    assert len(records) == 1


# ── Más cobertura para Fase 6.2 (líneas faltantes) ──


def test_clean_data_fill_mean(tmp_path):
    """Test mean fill strategy."""
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE raw_data (id INTEGER, data TEXT)")
    conn.execute("INSERT INTO raw_data VALUES (1, '{\"price\": 10}')")
    conn.execute("INSERT INTO raw_data VALUES (2, '{\"price\": null}')")
    conn.execute("INSERT INTO raw_data VALUES (3, '{\"price\": 20}')")
    conn.commit()
    conn.close()
    from etl.process import clean_data, load_raw_data

    df = load_raw_data(db)
    config = ProcessConfig(fill_null_strategy="mean")
    cleaned = clean_data(df, config)
    assert cleaned["price"].isna().sum() == 0
    assert cleaned["price"].iloc[1] == 15.0  # (10+20)/2


def test_clean_data_fill_median(tmp_path):
    """Test median fill strategy."""
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE raw_data (id INTEGER, data TEXT)")
    conn.execute("INSERT INTO raw_data VALUES (1, '{\"price\": 10}')")
    conn.execute("INSERT INTO raw_data VALUES (2, '{\"price\": null}')")
    conn.execute("INSERT INTO raw_data VALUES (3, '{\"price\": 30}')")
    conn.commit()
    conn.close()
    from etl.process import clean_data, load_raw_data

    df = load_raw_data(db)
    config = ProcessConfig(fill_null_strategy="median")
    cleaned = clean_data(df, config)
    assert cleaned["price"].isna().sum() == 0


def test_clean_data_outliers(tmp_path):
    """Test outlier detection (std threshold)."""
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE raw_data (id INTEGER, data TEXT)")
    conn.execute("INSERT INTO raw_data VALUES (1, '{\"val\": 100}')")
    conn.execute("INSERT INTO raw_data VALUES (2, '{\"val\": 1}')")
    conn.execute("INSERT INTO raw_data VALUES (3, '{\"val\": 2}')")
    conn.execute("INSERT INTO raw_data VALUES (4, '{\"val\": 3}')")
    conn.execute("INSERT INTO raw_data VALUES (5, '{\"val\": 4}')")
    conn.commit()
    conn.close()
    from etl.process import clean_data, load_raw_data

    df = load_raw_data(db)
    config = ProcessConfig(outlier_std_threshold=2)
    clean_data(df, config)  # should not crash, logs warnings


def test_save_processed_meta_only(tmp_path):
    """processed_data.save con solo columnas meta (sin data columns)."""
    df = pd.DataFrame(
        {
            "_source_url": ["http://x.com"],
            "_source_domain": ["x.com"],
            "_scraped_at": ["2026-07-20"],
        }
    )
    db = tmp_path / "test.db"
    save_processed(df, db)
    conn = sqlite3.connect(str(db))
    rows = conn.execute("SELECT COUNT(*) FROM processed_data").fetchone()[0]
    conn.close()
    assert rows == 0


def test_get_scrape_config_defaults():
    from etl.config import get_scrape_config

    cfg = get_scrape_config()
    assert cfg.timeout == 30
    assert cfg.db_path is not None


def test_get_scrape_config_overrides():
    from pathlib import Path

    from etl.config import get_scrape_config

    cfg = get_scrape_config(timeout=60, db_path=Path("custom.db"))
    assert cfg.timeout == 60
    assert "custom.db" in str(cfg.db_path)


def test_get_process_config_defaults():
    from etl.config import get_process_config

    cfg = get_process_config()
    assert cfg.fill_null_strategy == "drop"


def test_get_process_config_overrides():
    from etl.config import get_process_config

    cfg = get_process_config(fill_null_strategy="mean")
    assert cfg.fill_null_strategy == "mean"


def test_export_parquet(tmp_path):
    """Export parquet format."""
    from etl.config import ProcessConfig
    from etl.export import run_export

    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE processed_data (id INTEGER, title TEXT)")
    conn.execute("INSERT INTO processed_data VALUES (1, 'A')")
    conn.commit()
    conn.close()
    out = tmp_path / "out"
    out.mkdir()
    config = ProcessConfig(output_dir=out)
    run_export(db_path=db, config=config, fmt="parquet")
    assert list(out.glob("*.parquet"))


def test_export_no_rows(tmp_path, caplog):
    """Export with no data logs warning."""
    import logging

    caplog.set_level(logging.WARNING)
    from etl.config import ProcessConfig
    from etl.export import run_export

    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE processed_data (id INTEGER, title TEXT)")
    conn.commit()
    conn.close()
    out = tmp_path / "out"
    out.mkdir()
    config = ProcessConfig(output_dir=out)
    run_export(db_path=db, config=config, fmt="csv")
    assert "No hay datos" in caplog.text


def test_export_no_rows_parquet(tmp_path, caplog):
    """Export parquet with no data."""
    import logging

    caplog.set_level(logging.WARNING)
    from etl.config import ProcessConfig
    from etl.export import run_export

    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE processed_data (id INTEGER, title TEXT)")
    conn.commit()
    conn.close()
    out = tmp_path / "out"
    out.mkdir()
    config = ProcessConfig(output_dir=out)
    run_export(db_path=db, config=config, fmt="parquet")
    assert "No hay datos" in caplog.text


def test_scrape_empty_html(tmp_path):
    """extract_data con HTML vacío."""
    result = extract_data("", ["h1"], url="http://test.com", domain="test.com")
    assert result == []


def test_validate_db_path_missing_parent(tmp_path):
    """validate_db_path: directory doesn't exist."""
    from etl.config import validate_db_path

    with pytest.raises(ValueError, match="Directorio no existe"):
        validate_db_path(str(tmp_path / "nonexistent_dir" / "test.db"))


def test_save_processed_with_real_cols(tmp_path):
    """save_processed: crea columna REAL para datos numéricos."""
    df = pd.DataFrame(
        {
            "_source_url": ["http://x.com"],
            "_source_domain": ["x.com"],
            "_scraped_at": ["2026-07-20"],
            "price": [99.5],
        }
    )
    db = tmp_path / "test.db"
    save_processed(df, db)
    conn = sqlite3.connect(str(db))
    info = conn.execute("PRAGMA table_info(processed_data)").fetchall()
    col_names = [r[1].lower() for r in info]
    conn.close()
    assert "price" in col_names
