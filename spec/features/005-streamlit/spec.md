# Spec — Feature 005: Streamlit Dashboard

## Objetivo
Dashboard interactivo con Streamlit + Plotly (reemplaza/añade sobre Starlette).

## Requisitos
- `streamlit run dashboard/app.py`
- Sidebar: filtro dominio, fecha range
- Métricas: total records, dominios, URLs, date range
- Charts: bar (top items), doughnut (dominios), line (time series)
- Tabla paginada con búsqueda
- Export CSV/JSON desde la interfaz
- Dark theme

## Archivos
- `dashboard/streamlit_app.py` — App principal
- CLI: `python -m etl dashboard --mode streamlit`
