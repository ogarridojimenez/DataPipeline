"""Consultas SQL adaptadas al esquema columnar de processed_data."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger("dashboard.queries")


def get_stats(db_path: Path) -> dict[str, Any]:
    """Estadísticas generales de los datos procesados."""
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()

    try:
        c.execute(
            "SELECT COUNT(*) as total, COUNT(DISTINCT source_domain) as domains, "
            "COUNT(DISTINCT source_url) as urls FROM processed_data",
        )
        row = c.fetchone()
        total, domains, urls = row or (0, 0, 0)

        c.execute("SELECT MIN(scraped_at), MAX(scraped_at) FROM processed_data")
        date_row = c.fetchone()
        date_range = {
            "min": date_row[0] if date_row and date_row[0] else None,
            "max": date_row[1] if date_row and date_row[1] else None,
        }

        conn.close()
        return {
            "total_records": total,
            "unique_domains": domains,
            "unique_urls": urls,
            "date_range": date_range,
        }
    except sqlite3.OperationalError:
        conn.close()
        return {"total_records": 0, "unique_domains": 0, "unique_urls": 0, "date_range": {"min": None, "max": None}}


def get_top_items(
    db_path: Path,
    n: int = 10,
    column: str = "title",
) -> list[dict[str, Any]]:
    """Top N items ordenados por frecuencia."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    try:
        c.execute(
            f'SELECT "{column}", COUNT(*) as cnt FROM processed_data '
            f'WHERE "{column}" IS NOT NULL '
            f'GROUP BY "{column}" ORDER BY cnt DESC LIMIT ?',
            (n,),
        )
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return rows
    except sqlite3.OperationalError:
        conn.close()
        return []


def get_time_series(db_path: Path) -> list[dict[str, Any]]:
    """Conteo de registros agrupados por fecha."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    try:
        c.execute(
            "SELECT DATE(scraped_at) as day, COUNT(*) as cnt FROM processed_data GROUP BY day ORDER BY day",
        )
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return rows
    except sqlite3.OperationalError:
        conn.close()
        return []


def get_domain_breakdown(db_path: Path) -> list[dict[str, Any]]:
    """Distribución de registros por dominio."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    try:
        c.execute(
            "SELECT source_domain, COUNT(*) as cnt FROM processed_data GROUP BY source_domain ORDER BY cnt DESC",
        )
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return rows
    except sqlite3.OperationalError:
        conn.close()
        return []


def get_records(
    db_path: Path,
    domain: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Registros paginados, opcionalmente filtrados por dominio."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    try:
        if domain:
            c.execute(
                "SELECT * FROM processed_data WHERE source_domain = ? ORDER BY id DESC LIMIT ? OFFSET ?",
                (domain, limit, offset),
            )
        else:
            c.execute(
                "SELECT * FROM processed_data ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return rows
    except sqlite3.OperationalError:
        conn.close()
        return []


def get_column_names(db_path: Path) -> list[str]:
    """Obtiene las columnas disponibles en processed_data."""
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()

    try:
        c.execute("SELECT * FROM processed_data LIMIT 0")
        names = [desc[0] for desc in c.description]
        conn.close()
        return [
            n for n in names if not n.startswith("_") and n not in ("id", "source_url", "scraped_at", "source_domain")
        ]
    except sqlite3.OperationalError:
        conn.close()
        return []
