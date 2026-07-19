# 001 · ETL Core — Tareas

| # | Tarea | Depende de | Criterio de aceptación |
|---|-------|-----------|------------------------|
| 1 | Setup proyecto: `pyproject.toml`, requirements.txt, estructura dirs | — | `pip install -e .` funciona |
| 2 | `etl/config.py` — settings, UA rotation, DB path, rate limit config | 1 | Config se instancia con defaults |
| 3 | `etl/__main__.py` + `etl/__init__.py` — CLI argparse con scrape/process/export/help | 1 | `python -m etl --help` muestra subcomandos |
| 4 | `etl/scrape.py` — httpx async + selectolax + rate limit + retry | 2,3 | Scrapea URL de prueba y guarda en SQLite |
| 5 | `etl/process.py` — pandas cleaning (dedup, nulls, outliers) | 4 | Procesa datos raw y genera clean_data |
| 6 | `etl/export.py` — SQLite + CSV + JSON writer | 4 | Export genera 3 archivos válidos |
| 7 | `tests/test_scrape.py` — unit tests con HTML mock | 4 | Tests pasan con pytest |
| 8 | `tests/test_process.py` — unit tests con DataFrame mock | 5 | Tests pasan |
| 9 | Integración end-to-end: scrape → process → export | 5,6 | Flujo completo funciona |
| 10 | README.md con uso y ejemplos | 9 | Documenta install + uso |

## Validación
- [ ] Cada criterio de aceptación arriba se cumple
- [ ] `pytest tests/` pasa
- [ ] `python -m etl scrape <test-url> --selectors "h1" funciona`
- [ ] Roadmap.md actualizado
