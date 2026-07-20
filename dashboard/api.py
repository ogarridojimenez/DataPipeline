"""API REST FastAPI para DataPipeline.

Endpoints:
- GET  /data     → datos paginados con filtros
- GET  /stats    → estadísticas agregadas
- POST /scrape   → ejecuta scraping asíncrono
- GET  /health   → health check del sistema
- GET  /metrics  → métricas Prometheus
"""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query

from dashboard.queries import get_stats as _get_db_stats

app = FastAPI(
    title="DataPipeline API",
    version="0.4.0",
    description="REST API para el pipeline ETL",
)

DB_PATH: Path = Path("data/pipeline.db")


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _get_conn(db_path: Path | None = None) -> sqlite3.Connection:
    p = db_path or DB_PATH
    if not p.exists():
        raise HTTPException(404, f"Base de datos no encontrada: {p}")
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    return conn


# ─── Data ─────────────────────────────────────────────────────────────────────


@app.get("/data")
def list_data(
    table: str = Query("raw_data", description="Tabla (raw_data|processed_data)"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    domain: str | None = Query(None, description="Filtrar por dominio"),
    sort: str | None = Query(None, description="Campo para ordenar"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
):
    """Retorna registros paginados de raw_data o processed_data."""
    if table not in ("raw_data", "processed_data"):
        raise HTTPException(400, f"Tabla inválida: {table}")

    conn = _get_conn()
    try:
        where_clauses = []
        params: list[Any] = []

        if domain:
            where_clauses.append("source LIKE ?")
            params.append(f"%{domain}%")

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        order_sql = ""
        if sort:
            order_sql = f' ORDER BY "{sort}" {order.upper()}'

        # Total count
        total = conn.execute(f"SELECT COUNT(*) FROM {table}{where_sql}", params).fetchone()[0]

        # Data
        rows = conn.execute(
            f"SELECT * FROM {table}{where_sql}{order_sql} LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "rows": [dict(r) for r in rows],
        }
    finally:
        conn.close()


# ─── Stats ────────────────────────────────────────────────────────────────────


@app.get("/stats")
def stats(db_path: str | None = Query(None, description="Ruta SQLite opcional")):
    """Retorna estadísticas agregadas del pipeline."""
    p = Path(db_path) if db_path else DB_PATH
    if not p.exists():
        raise HTTPException(404, f"Base de datos no encontrada: {p}")
    result = _get_db_stats(p)
    if not result:
        raise HTTPException(404, "No hay datos en la base de datos")
    return result


# ─── Scrape ───────────────────────────────────────────────────────────────────


@app.post("/scrape")
async def trigger_scrape(
    urls: list[str],
    selectors: list[str],
    db_path: str | None = None,
    timeout: int = 30,
):
    """Ejecuta scraping asíncrono. Retorna inmediatamente con un job_id."""
    from etl.config import get_scrape_config
    from etl.scrape import run_scrape

    config = get_scrape_config(
        timeout=timeout,
        db_path=Path(db_path) if db_path else DB_PATH,
        webhook_url=None,
    )

    # Ejecutar en background
    async def _run():
        try:
            total_rows = await run_scrape(urls, selectors, config)
            return {"status": "completed", "total_rows": total_rows}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    task = asyncio.create_task(_run())
    return {
        "status": "accepted",
        "urls": urls,
        "selectors": selectors,
        "job_id": id(task),
    }


# ─── Health ───────────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    """Health check del sistema."""
    db = DB_PATH
    db_exists = db.exists()
    db_size = db.stat().st_size if db_exists else 0

    # Último registro
    last_scrape = None
    if db_exists:
        conn = _get_conn()
        try:
            row = conn.execute("SELECT scraped_at FROM raw_data ORDER BY scraped_at DESC LIMIT 1").fetchone()
            if row:
                last_scrape = row["scraped_at"]
        finally:
            conn.close()

    # Tiempo de actividad (desde inicio del proceso)
    uptime_seconds = (datetime.now(UTC) - _start_time).total_seconds()

    return {
        "status": "ok",
        "version": "0.4.0",
        "db": {
            "exists": db_exists,
            "path": str(db.absolute()),
            "size_bytes": db_size,
            "size_mb": round(db_size / 1_048_576, 2),
        },
        "last_scrape": last_scrape,
        "uptime_seconds": round(uptime_seconds, 1),
    }


_start_time = datetime.now(UTC)


# ─── Metrics (Prometheus) ─────────────────────────────────────────────────────


@app.get("/metrics")
def metrics():
    """Métricas estilo Prometheus para el pipeline."""

    db = DB_PATH
    lines: list[str] = []
    lines.append("# HELP etl_health_status Estado del pipeline (1=ok, 0=error)")
    lines.append("# TYPE etl_health_status gauge")
    lines.append(f"etl_health_status {1 if db.exists() else 0}")

    if db.exists():
        conn = _get_conn()
        try:
            # Conteos por tabla
            for table in ("raw_data", "processed_data"):
                t = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                lines.append(f"# HELP etl_{table}_total Total de registros en {table}")
                lines.append(f"# TYPE etl_{table}_total gauge")
                lines.append(f"etl_{table}_total {t}")

            # Tamaño DB
            lines.append("# HELP etl_db_size_bytes Tamaño de la base de datos")
            lines.append("# TYPE etl_db_size_bytes gauge")
            lines.append(f"etl_db_size_bytes {db.stat().st_size}")

            # Último scrape (timestamp UNIX)
            row = conn.execute("SELECT scraped_at FROM raw_data ORDER BY scraped_at DESC LIMIT 1").fetchone()
            if row:
                try:
                    ts = datetime.fromisoformat(row["scraped_at"]).timestamp()
                    lines.append("# HELP etl_last_scrape_timestamp Último scrape (unix ts)")
                    lines.append("# TYPE etl_last_scrape_timestamp gauge")
                    lines.append(f"etl_last_scrape_timestamp {int(ts)}")
                except (ValueError, TypeError):
                    pass
        finally:
            conn.close()

    lines.append("# HELP etl_uptime_seconds Segundos desde el inicio")
    lines.append("# TYPE etl_uptime_seconds gauge")
    lines.append(f"etl_uptime_seconds {int((datetime.now(UTC) - _start_time).total_seconds())}")

    return "\n".join(lines) + "\n", 200, {"Content-Type": "text/plain; charset=utf-8"}


# ─── CLI mode ─────────────────────────────────────────────────────────────────


def serve(host: str = "127.0.0.1", port: int = 8000, db_path: str = "data/pipeline.db") -> None:
    """Inicia el servidor API."""
    import uvicorn

    global DB_PATH
    DB_PATH = Path(db_path)

    print(f"🌐 API DataPipeline: http://{host}:{port}")
    print(f"   Docs: http://{host}:{port}/docs")
    uvicorn.run(app, host=host, port=port)
