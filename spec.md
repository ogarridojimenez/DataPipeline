# DataPipeline — Especificación del Proyecto

## 🎯 Propósito
Pipeline ETL en Python: web scraping → procesamiento → visualización. Data engineering puro, sin ciberseguridad.

## Stack
Python 3.13 + httpx + selectolax (HTML parsing) + pandas + SQLite + Streamlit + Docker + GitHub Actions

## Lo que demuestra
- **Web scraping ético** con rate limiting + rotación User-Agent
- **Procesamiento async** con httpx + asyncio
- **Limpieza de datos** con pandas (nulls, dups, formatos)
- **Visualización** con Streamlit dashboard interactivo
- **Persistencia** SQLite + export CSV/JSON
- **Automatización** GitHub Actions schedule semanal
- **Docker** reproducible

## Ejemplo
```bash
python -m etl scrape "https://tienda-ejemplo.com/productos" \
  --selectors "h2.title" ".price" ".stock"
python -m etl process --clean --dedup --fill-missing
streamlit run dashboard/app.py
```
