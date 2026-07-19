# DataPipeline

**Pipeline ETL en Python:** scraping asíncrono → procesamiento → exportación.

## Quick Start

```bash
# Instalar
pip install -e ".[dev]"

# Scrape
python -m etl scrape "https://ejemplo.com/productos" --selectors "h2.title" ".price"

# Procesar
python -m etl process

# Exportar
python -m etl export

# Tests
pytest tests/

# Dashboard (requiere extras)
pip install -e ".[dashboard]"
streamlit run dashboard/app.py
```

## Arquitectura

```
🌐 Scraping (httpx async + lxml)
   → Rate limit por dominio, retry con backoff
   → User-Agent rotación
      ↓
🧹 Procesamiento (stdlib)
   → Deduplicación, limpieza nulls, normalización
   → Detección de outliers (>3 std dev)
      ↓
💾 Exportación
   → SQLite + CSV + JSON
```

## Stack

| Componente | Tecnología |
|------------|-----------|
| HTTP async | httpx |
| HTML parsing | lxml (CSS selectors) |
| Data processing | stdlib + statistics |
| Storage | SQLite + CSV + JSON |
| Testing | pytest + pytest-asyncio |
| Dashboard | Streamlit + Plotly (optional) |

## Configuración

| Variable | Default | Descripción |
|----------|---------|-------------|
| `ETL_DB_PATH` | `data/pipeline.db` | Ruta SQLite |
| `ETL_TIMEOUT` | `30` | Timeout request (s) |
| `ETL_RATE_LIMIT` | `1.0` | Delay entre requests (s) |
| `ETL_OUTPUT_DIR` | `data/processed` | Directorio export |

## License

MIT
