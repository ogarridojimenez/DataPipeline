# Tech Stack — DataPipeline

## Lenguaje
- Python 3.11+ (disponible en entorno)

## Dependencias core
| Librería | Versión | Uso |
|----------|---------|-----|
| httpx | latest | HTTP async client |
| selectolax | latest | HTML parsing (Lexbor engine) |
| pandas | latest | Data processing |
| streamlit | latest | Dashboard web |
| plotly | latest | Gráficos interactivos |

## Almacenamiento
- SQLite (stdlib) — almacenamiento local
- CSV/JSON — exportación

## DevOps
- Docker — reproducibilidad
- GitHub Actions — CI + schedule semanal

## Comandos
| Acción | Comando |
|--------|---------|
| Install | `pip install -r requirements.txt` |
| Scrape | `python -m etl scrape <url> --selectors <css>` |
| Process | `python -m etl process` |
| Dashboard | `streamlit run dashboard/app.py` |
| Test | `pytest tests/` |
| Docker | `docker build -t datapipeline .` |

## Convenciones
- snake_case para archivos y funciones
- Type hints en funciones públicas
- Docstrings en módulos públicos

## Límites duros
- Máx 1 request/segundo por dominio (rate limit)
- User-Agent rotatorio obligatorio
- No scrapear sitios con login/sesión (sin auth)
- No almacenar datos personales (GDPR-lite)
