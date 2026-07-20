"""Queries SQLite para el dashboard."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


def get_stats(db_path: Path) -> dict[str, Any]:
    """Estadísticas generales."""
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM processed_data")
    total = c.fetchone()[0]

    c.execute("SELECT COUNT(DISTINCT source_domain) FROM processed_data")
    domains = c.fetchone()[0]

    c.execute("SELECT MIN(scraped_at), MAX(scraped_at) FROM processed_data")
    min_date, max_date = c.fetchone()

    c.execute("SELECT COUNT(DISTINCT source_url) FROM processed_data")
    urls = c.fetchone()[0]

    conn.close()
    return {
        "total_records": total,
        "unique_domains": domains,
        "unique_urls": urls,
        "date_range": {"min": min_date, "max": max_date},
    }


def get_top_items(db_path: Path, n: int = 10, column: str = "title") -> list[dict[str, Any]]:
    """Top N items por frecuencia en una columna."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    query = f"""
        SELECT json_extract(data, '$.{column}') as val, COUNT(*) as cnt
        FROM processed_data
        WHERE json_extract(data, '$.{column}') IS NOT NULL
          AND json_extract(data, '$.{column}') != ''
        GROUP BY val
        ORDER BY cnt DESC
        LIMIT ?
    """
    try:
        c.execute(query, (n,))
        rows = [dict(r) for r in c.fetchall()]
    except Exception:
        rows = []

    conn.close()
    return rows


def get_time_series(db_path: Path) -> list[dict[str, Any]]:
    """Registros por día."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
        SELECT DATE(scraped_at) as date, COUNT(*) as count
        FROM processed_data
        GROUP BY date
        ORDER BY date
    """)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_domain_breakdown(db_path: Path) -> list[dict[str, Any]]:
    """Registros por dominio."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
        SELECT source_domain as domain, COUNT(*) as count
        FROM processed_data
        GROUP BY source_domain
        ORDER BY count DESC
    """)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_records(db_path: Path, domain: str | None = None, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    """Registros paginados, opcionalmente filtrados por dominio."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    if domain:
        c.execute(
            """
            SELECT id, source_url, source_domain, data, scraped_at
            FROM processed_data
            WHERE source_domain = ?
            ORDER BY id DESC LIMIT ? OFFSET ?
        """,
            (domain, limit, offset),
        )
    else:
        c.execute(
            """
            SELECT id, source_url, source_domain, data, scraped_at
            FROM processed_data
            ORDER BY id DESC LIMIT ? OFFSET ?
        """,
            (limit, offset),
        )

    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_column_names(db_path: Path) -> list[str]:
    """Obtiene las columnas disponibles en los datos JSON."""
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()

    c.execute("SELECT data FROM processed_data LIMIT 1")
    row = c.fetchone()
    conn.close()

    if not row:
        return []

    data = json.loads(row[0])
    if isinstance(data, dict):
        return list(data.keys())
    return []
