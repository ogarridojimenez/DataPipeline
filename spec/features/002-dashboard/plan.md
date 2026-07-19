# Plan — Feature 002: Dashboard

## Arquitectura
```
Browser ←→ Starlette (ASGI) ←→ SQLite
  ↑              ↑
  │         Jinja2Templates
  │              ↓
  └────── HTML + Chart.js (CDN)
```

## Componentes

### 1. `dashboard/app.py` — Starlette ASGI
- Rutas: `/`, `/api/stats`, `/api/top`, `/api/export`
- Jinja2Templates para HTML
- JSONResponse para APIs

### 2. `dashboard/queries.py` — SQLite queries
- `get_stats(db)` → total rows, domains, date range
- `get_top_items(db, n)` → top N items by frequency
- `get_time_series(db)` → items per day
- `get_domain_breakdown(db)` → items per domain
- `get_records(db, domain, limit)` → paginated records

### 3. `dashboard/templates/` — Jinja2 HTML
- `base.html` — layout + Chart.js CDN
- `index.html` — dashboard principal

### 4. `dashboard/static/style.css` — Minimal CSS

## Decisiones
- **Starlette over Flask**: async nativo, ya instalado
- **Chart.js CDN**: el browser del usuario tiene internet; el server no necesita
- **No pandas**: procesamiento con stdlib + sqlite3

## Endpoints
| Método | Ruta | Retorna |
|--------|------|---------|
| GET | `/` | HTML dashboard |
| GET | `/api/stats` | JSON stats |
| GET | `/api/top?n=10` | JSON top items |
| GET | `/api/timeseries` | JSON time series |
| GET | `/api/domains` | JSON domain breakdown |
| GET | `/api/records?domain=&limit=50` | JSON records |
| GET | `/api/export?format=csv` | CSV download |
