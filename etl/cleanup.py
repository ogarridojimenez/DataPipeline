"""Limpieza de datos antiguos (data retention / cleanup).

Purga registros de `raw_data` y `processed_data` según antigüedad.

Uso:
    python -m etl cleanup --days 30
    python -m etl cleanup --days 7 --dry-run
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path


def cleanup_db(
    db_path: Path,
    days: int = 30,
    dry_run: bool = False,
    verbose: bool = True,
) -> dict[str, int]:
    """Purga registros antiguos de la base de datos.

    Args:
        db_path: Ruta a la base de datos SQLite.
        days: Registros más antiguos que N días serán eliminados.
        dry_run: Si True, solo cuenta sin eliminar.
        verbose: Si True, imprime resumen.

    Returns:
        Dict con conteos: raw_rows, processed_rows.
    """
    cutoff = datetime.now(UTC) - timedelta(days=days)
    cutoff_iso = cutoff.isoformat()

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Obtener tablas disponibles
    tables = [r["name"] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")]

    counts: dict[str, int] = {}

    for table in tables:
        if table not in ("raw_data", "processed_data"):
            continue
        # Contar registros antiguos
        count = cursor.execute(
            f"SELECT COUNT(*) FROM {table} WHERE scraped_at < ?",
            (cutoff_iso,),
        ).fetchone()[0]

        counts[table] = count

        if count == 0:
            if verbose:
                print(f"  ✓ {table}: sin registros antiguos")
            continue

        if dry_run:
            if verbose:
                print(f"  ~ {table}: {count} registros serían eliminados (dry-run)")
        else:
            cursor.execute(f"DELETE FROM {table} WHERE scraped_at < ?", (cutoff_iso,))
            conn.commit()
            if verbose:
                print(f"  ✓ {table}: {count} registros eliminados")

    conn.close()
    return counts
