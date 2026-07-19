"""Dashboard ASGI — Starlette + Jinja2 + Chart.js."""

import csv
import io
import json
from pathlib import Path

from starlette.applications import Starlette
from starlette.responses import JSONResponse, HTMLResponse, StreamingResponse
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from dashboard.queries import (
    get_stats, get_top_items, get_time_series,
    get_domain_breakdown, get_records, get_column_names,
)

DB_PATH = Path(__file__).parent.parent / "data" / "pipeline.db"
TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def get_db():
    return DB_PATH


# --- Páginas HTML ---

async def homepage(request):
    db = get_db()
    if not db.exists():
        return HTMLResponse("<h1>No data yet. Run the ETL pipeline first.</h1>", status_code=404)

    stats = get_stats(db)
    top = get_top_items(db, 10, "title")
    timeseries = get_time_series(db)
    domains = get_domain_breakdown(db)
    columns = get_column_names(db)

    return templates.TemplateResponse(request, "index.html", {
        "stats": stats,
        "top_items": top,
        "timeseries": timeseries,
        "domains": domains,
        "columns": columns,
    })


# --- API JSON ---

async def api_stats(request):
    db = get_db()
    if not db.exists():
        return JSONResponse({"error": "No data"}, status_code=404)
    return JSONResponse(get_stats(db))


async def api_top(request):
    db = get_db()
    if not db.exists():
        return JSONResponse({"error": "No data"}, status_code=404)
    n = int(request.query_params.get("n", 10))
    col = request.query_params.get("column", "title")
    return JSONResponse(get_top_items(db, n, col))


async def api_timeseries(request):
    db = get_db()
    if not db.exists():
        return JSONResponse({"error": "No data"}, status_code=404)
    return JSONResponse(get_time_series(db))


async def api_domains(request):
    db = get_db()
    if not db.exists():
        return JSONResponse({"error": "No data"}, status_code=404)
    return JSONResponse(get_domain_breakdown(db))


async def api_records(request):
    db = get_db()
    if not db.exists():
        return JSONResponse({"error": "No data"}, status_code=404)
    domain = request.query_params.get("domain")
    limit = int(request.query_params.get("limit", 50))
    offset = int(request.query_params.get("offset", 0))
    return JSONResponse(get_records(db, domain, limit, offset))


async def api_export(request):
    db = get_db()
    if not db.exists():
        return JSONResponse({"error": "No data"}, status_code=404)

    fmt = request.query_params.get("format", "csv")
    domain = request.query_params.get("domain")
    records = get_records(db, domain, limit=10000)

    if fmt == "json":
        data = [json.loads(r["data"]) for r in records]
        return JSONResponse(data)

    # CSV
    if not records:
        return StreamingResponse(io.BytesIO(b""), media_type="text/csv",
                                headers={"Content-Disposition": "attachment; filename=export.csv"})

    first = json.loads(records[0]["data"])
    if isinstance(first, dict):
        headers = list(first.keys())
    else:
        headers = ["value"]

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for r in records:
        data = json.loads(r["data"])
        if isinstance(data, dict):
            writer.writerow(data)

    content = output.getvalue().encode("utf-8")
    return StreamingResponse(
        io.BytesIO(content),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=export.csv"},
    )


# --- App ---

routes = [
    Route("/", homepage),
    Route("/api/stats", api_stats),
    Route("/api/top", api_top),
    Route("/api/timeseries", api_timeseries),
    Route("/api/domains", api_domains),
    Route("/api/records", api_records),
    Route("/api/export", api_export),
    Mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static"),
]

app = Starlette(debug=True, routes=routes)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("dashboard.app:app", host="0.0.0.0", port=8501, reload=True)
