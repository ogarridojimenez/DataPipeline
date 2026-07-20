# Changelog

Todas las versiones notables de DataPipeline se documentan aquí.

Formato basado en [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
y el proyecto sigue [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-07-20

### Añadido
- Secretos: webhook URL desde variable de entorno `ETL_WEBHOOK_URL`
- Validación de ruta DB en dashboard (`validate_db_path`)
- Docker multi-etapa (imagen ~180MB)
- CHANGELOG.md con versionado semántico
- CI: Ruff lint automático en PRs

### Cambiado
- `run_export()` ahora acepta `df` opcional (evita re-lectura SQLite)
- `get_scrape_config()` integra env vars ETL_WEBHOOK_URL + ETL_CONCURRENCY
- Dashboard: sanitiza y valida ruta de base de datos en sidebar

### Mejorado
- Migración a pytest (37 tests, +12 nuevos)
- Refactor: lógica JSON-expand centralizada en `process.expand_json_records()`
- Logging: reemplazados todos los `print()` por `logging`
- Type hints completos en `export.py`, `notify.py`, `dashboard/`
- Linting unificado con Ruff + pre-commit

### Técnico
- Ruff (E, W, F, I, UP, N) + ruff format configurados
- pre-commit hooks en repositorio
- CI en `.github/workflows/ci.yml`

## [0.1.0] - 2026-06

### Añadido
- Scraping asíncrono con httpx (10 features)
- Procesamiento y limpieza de datos
- Exportación a CSV / JSON / Parquet
- Dashboard Streamlit + Starlette
- Notificaciones webhook Slack/Discord
- Scheduler con schedule.yml
- 25 tests base

[0.2.0]: https://github.com/ogarridojimenez/DataPipeline/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/ogarridojimenez/DataPipeline/releases/tag/v0.1.0
