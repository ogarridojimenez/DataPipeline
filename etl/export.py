"""Fase de exportación: SQLite → CSV + JSON + Parquet."""

from __future__ import annotations

import csv
import json
import logging
import sqlite3
from pathlib import Path

import pandas as pd

from etl.config import ProcessConfig

logger = logging.getLogger("etl.export")


def load_processed(db_path: Path) -> tuple[list[str], list[dict]]:
    """Carga datos procesados desde SQLite. Retorna (columnas, filas)."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM processed_data")
    except Exception:
        logger.warning("Tabla 'processed_data' no existe, usando raw_data")
        conn.close()
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM raw_data")

    columns = [desc[0] for desc in cursor.description]
    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return columns, rows


def load_processed_df(db_path: Path) -> pd.DataFrame:
    """Carga datos procesados desde SQLite y retorna un DataFrame de pandas.

    Primero intenta con la tabla ``processed_data``; si no existe, usa ``raw_data``.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        df = pd.read_sql_query("SELECT * FROM processed_data", conn)
    except Exception:
        logger.warning("Tabla 'processed_data' no existe, usando raw_data")
        conn.close()
        conn = sqlite3.connect(str(db_path))
        df = pd.read_sql_query("SELECT * FROM raw_data", conn)
    conn.close()
    return df


def run_export(db_path: Path, config: ProcessConfig, fmt: str = "both") -> None:
    """Exporta datos procesados a CSV, JSON y/o Parquet."""
    config.output_dir.mkdir(parents=True, exist_ok=True)

    if fmt == "parquet":
        # Para parquet usamos pandas + pyarrow
        df = load_processed_df(db_path)
        if df.empty:
            logger.warning("No hay datos para exportar")
            return
        base_name = "datapipeline_export"
        parquet_path = config.output_dir / f"{base_name}.parquet"
        df.to_parquet(parquet_path, index=False)
        logger.info("Parquet: %s (%d filas)", parquet_path, len(df))
        logger.info("Exportación completa (%s)", fmt)
        return

    columns, rows = load_processed(db_path)
    if not rows:
        logger.warning("No hay datos para exportar")
        return

    base_name = "datapipeline_export"

    if fmt in ("csv", "both"):
        csv_path = config.output_dir / f"{base_name}.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        logger.info("CSV: %s (%d filas)", csv_path, len(rows))

    if fmt in ("json", "both"):
        json_path = config.output_dir / f"{base_name}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2, ensure_ascii=False, default=str)
        logger.info("JSON: %s (%d registros)", json_path, len(rows))

    logger.info("Exportación completa (%s)", fmt)
