"""Fase de exportación: SQLite → CSV + JSON (stdlib)."""

from __future__ import annotations

import csv
import io
import json
import logging
import sqlite3
from pathlib import Path

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


def run_export(db_path: Path, config: ProcessConfig, fmt: str = "both") -> None:
    """Exporta datos procesados a CSV y/o JSON."""
    config.output_dir.mkdir(parents=True, exist_ok=True)

    columns, rows = load_processed(db_path)
    if not rows:
        print("⚠ No hay datos para exportar")
        return

    base_name = "datapipeline_export"

    if fmt in ("csv", "both"):
        csv_path = config.output_dir / f"{base_name}.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        print(f"✓ CSV: {csv_path} ({len(rows)} filas)")

    if fmt in ("json", "both"):
        json_path = config.output_dir / f"{base_name}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2, ensure_ascii=False, default=str)
        print(f"✓ JSON: {json_path} ({len(rows)} registros)")

    print(f"✓ Exportación completa ({fmt})")
