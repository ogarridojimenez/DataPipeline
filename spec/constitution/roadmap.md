# Roadmap — DataPipeline

## Hecho ✅
| # | Feature | Descripción | Commit |
|---|---------|-------------|--------|
| 001 | ETL Core | httpx + selectolax + pandas + export | 71738f0 |
| 002 | Dashboard | Starlette + Jinja2 + Chart.js | d874d40 |
| 003 | Docker + CI | Dockerfile + GitHub Actions | ab87248 |
| 004 | Restore deps | pandas + selectolax en ETL core | d5fd521 |
| 005 | Streamlit | Streamlit + Plotly dashboard | 54b72c9 |

## Backlog 💡
- Múltiples targets simultáneos
- Exportación a más formatos (parquet)
- Alerts por webhook cuando hay cambios significativos
- Deduplicación incremental (no re-scrape completo)
