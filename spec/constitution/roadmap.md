# Roadmap — DataPipeline

## Hecho ✅
| # | Feature | Descripción | Commit |
|---|---------|-------------|--------|
| 001 | ETL Core | Scraping (httpx+lxml) + process + export + CLI | 71738f0 |

## Siguiente 🔜
| # | Feature | Descripción |
|---|---------|-------------|
| 002 | Dashboard | Streamlit + Plotly visualización interactiva |
| 003 | Docker + CI | Dockerfile + GitHub Actions schedule |

## Backlog 💡
- Múltiples targets simultáneos
- Exportación a más formatos (parquet)
- Alerts por webhook cuando hay cambios significativos
- Deduplicación incremental (no re-scrape completo)
- pandas para procesamiento avanzado (requiere instalación)
