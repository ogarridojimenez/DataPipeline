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


def load_processed(db_path: Path, since: str | None = None) -> tuple[list[str], list[dict]]:
    """Carga datos procesados desde SQLite. Retorna (columnas, filas)."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        query = "SELECT * FROM processed_data"
        params: list = []
        if since:
            query += " WHERE scraped_at >= ?"
            params.append(since)
        cursor.execute(query, params)
    except Exception:
        logger.warning("Tabla 'processed_data' no existe, usando raw_data")
        conn.close()
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        query = "SELECT * FROM raw_data"
        if since:
            query += " WHERE scraped_at >= ?"
            cursor.execute(query, [since])
        else:
            cursor.execute(query)

    columns = [desc[0] for desc in cursor.description]
    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return columns, rows


def load_processed_df(db_path: Path, since: str | None = None) -> pd.DataFrame:
    """Carga datos procesados desde SQLite y retorna un DataFrame de pandas."""
    conn = sqlite3.connect(str(db_path))
    try:
        query = "SELECT * FROM processed_data"
        if since:
            query += " WHERE scraped_at >= ?"
            df = pd.read_sql_query(query, conn, params=[since])
        else:
            df = pd.read_sql_query(query, conn)
    except Exception:
        logger.warning("Tabla 'processed_data' no existe, usando raw_data")
        conn.close()
        conn = sqlite3.connect(str(db_path))
        query = "SELECT * FROM raw_data"
        if since:
            query += " WHERE scraped_at >= ?"
            df = pd.read_sql_query(query, conn, params=[since])
        else:
            df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def run_export(
    db_path: Path | None = None,
    config: ProcessConfig | None = None,
    fmt: str = "both",
    df: pd.DataFrame | None = None,
    since: str | None = None,
) -> None:
    """Exporta datos procesados a CSV, JSON y/o Parquet.

    Args:
        db_path: Ruta SQLite (ignorado si se pasa df).
        config: Configuración de procesamiento (usa defaults si None).
        fmt: Formato de exportación (csv, json, both, parquet).
        df: DataFrame opcional para evitar re-lectura de SQLite.
        since: Filtro ISO (ej: '2026-07-01') — solo exporta registros >= esta fecha.
    """
    if config is None:
        config = ProcessConfig()
    config.output_dir.mkdir(parents=True, exist_ok=True)

    if fmt == "parquet":
        if df is None:
            df = load_processed_df(db_path or Path("data/pipeline.db"), since=since)
        if df.empty:
            logger.warning("No hay datos para exportar")
            return
        base_name = "datapipeline_export"
        parquet_path = config.output_dir / f"{base_name}.parquet"
        df.to_parquet(parquet_path, index=False)
        logger.info("Parquet: %s (%d filas)", parquet_path, len(df))
        logger.info("Exportación completa (%s)", fmt)
        return

    columns, rows = load_processed(db_path or Path("data/pipeline.db"), since=since)
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
