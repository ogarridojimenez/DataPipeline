"""Tests para etl.config — configuración del pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from etl.config import ProcessConfig, validate_db_path


def test_default_config():
    c = ProcessConfig()
    assert c.fill_null_strategy == "drop"
    assert c.outlier_std_threshold == 3.0
    assert c.output_dir == Path("data/processed")


def test_custom_config():
    c = ProcessConfig(fill_null_strategy="mean", outlier_std_threshold=2.0, output_dir=Path("custom"))
    assert c.fill_null_strategy == "mean"
    assert c.outlier_std_threshold == 2.0
    assert c.output_dir == Path("custom")


def test_validate_db_path_valid(tmp_path):
    db = tmp_path / "test.db"
    db.touch()
    result = validate_db_path(str(db))
    assert result == db  # returns resolved Path


def test_validate_db_path_invalid_extension(tmp_path):
    db = tmp_path / "test.txt"
    with pytest.raises(ValueError, match="Extensión inválida"):
        validate_db_path(str(db))


def test_validate_db_path_not_found(tmp_path):
    db = tmp_path / "nonexistent.db"
    result = validate_db_path(str(db))
    assert result is None  # returns None si no existe


def test_validate_db_path_none():
    result = validate_db_path(None)
    assert result is None
