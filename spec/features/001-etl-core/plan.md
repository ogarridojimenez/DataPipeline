# 001 · ETL Core — Plan

## Enfoque
CLI modular con subcomandos (scrape, process, export). Cada fase es un módulo independiente que comparte SQLite como almacenamiento intermedio.

## Arquitectura
```
CLI (click/argparse)
├── etl/scrape.py      ← httpx async + selectolax
├── etl/process.py     ← pandas cleaning
├── etl/export.py      ← SQLite + CSV + JSON
├── etl/config.py      ← rate limit, UA, DB path
└── etl/__init__.py
```

Flujo de datos:
```
URL → httpx.get → HTML → selectolax.parse → raw_records[]
  → pandas.DataFrame → clean_df
    → SQLite / CSV / JSON
```

## Modelo de datos
```sql
CREATE TABLE scraped_data (
    id INTEGER PRIMARY KEY,
    source_url TEXT,
    scraped_at TIMESTAMP,
    raw_json TEXT,       -- datos extraídos sin procesar
    processed BOOLEAN DEFAULT FALSE
);

CREATE TABLE clean_data (
    id INTEGER PRIMARY KEY,
    source_id INTEGER,  -- FK → scraped_data
    cleaned_json TEXT,
    cleaned_at TIMESTAMP
);
```

## Contratos
| Módulo | Input | Output |
|--------|-------|--------|
| scrape | URL + selectors | records[] → SQLite |
| process | SQLite raw | cleaned DataFrame → SQLite + CSV + JSON |

## Implementación
1. `etl/__init__.py` + `etl/__main__.py` — CLI entry point
2. `etl/config.py` — settings, UA rotation, DB path
3. `etl/scrape.py` — httpx async + selectolax + rate limit
4. `etl/process.py` — pandas cleaning pipeline
5. `etl/export.py` — SQLite + CSV + JSON writer
6. `tests/` — unit tests por módulo

## Decisiones
- **selectolax > BeautifulSoup** — 10x más rápido, Lexbor engine
- **httpx > aiohttp** — API más limpia, sync+async, nativo Python
- **SQLite > PostgreSQL** — zero config, portátil, suficiente para portfolio
- **argparse > click** — zero dependencies extra

## Riesgos
- **Sitios con JS rendering** — mitigación: documentar limitación, solo HTML estático
- **Rate limit insuficiente** — mitigación: configurable por flag `--delay`
- **selectolax compilation** — mitigación: wheels disponibles para Python 3.11
