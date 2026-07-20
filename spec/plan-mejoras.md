# Plan de mejora — DataPipeline

## Visión general

Basado en análisis profundo del código (~2.700 LOC, 10 features, 25 tests).
**6 fases**, implementación secuencial. Cada fase produce código funcional + tests + commit.

---

## Fase 1 — Fundación (deuda técnica)

| # | Tarea | Esfuerzo | Descripción |
|---|-------|----------|-------------|
| 1.1 | **Migrar tests a pytest** | 1h | Unificar `run_tests.py` (custom runner) + `tests/` (pytest) → pytest puro. Elimina bug de closure `json`, da reports reales, JUnit XML |
| 1.2 | **Ruff + pre-commit** | 30min | Configurar Ruff (lint+format+isort) + hook pre-commit. Código consistente sin discusiones |
| 1.3 | **Eliminar duplicación JSON-expand** | 30min | Mover `json.loads(row["data"])` a `etl/process.expand_json_column()`. Dashboard y export lo importan |
| 1.4 | **Unificar logging** | 1h | Reemplazar todos los `print()` → `logging`. Handler por defecto en `__main__.py`, `--verbose` flag global |
| 1.5 | **Type hints completos** | 1h | Completar tipos faltantes en `export.py`, `notify.py`, `dashboard/`. Mypy strict en CI |

**Entregable:** Código limpio, tipado, 100% pytest, lint pasa, CI unificado.
**Tests:** ~30 tests, cobertura ~65%.

---

## Fase 2 — Endurecimiento (seguridad + arquitectura)

| # | Tarea | Esfuerzo | Descripción |
|---|-------|----------|-------------|
| 2.1 | **Gestión de secretos** | 30min | `--webhook` desde variable de entorno `ETL_WEBHOOK_URL`. CLI lo lee como fallback. Protege URL de `ps` |
| 2.2 | **Validación DB path** | 30min | Sanitizar input de DB en dashboard (no permitir rutas fuera del proyecto, validar extensión `.db`) |
| 2.3 | **Repositorio único de datos** | 30min | `run_export` acepta DataFrame opcional. Si ya se procesó, no re-lee SQLite |
| 2.4 | **Docker multi-etapa** | 30min | Build / runtime separados. Imagen de ~1GB → ~200MB |
| 2.5 | **CHANGELOG.md** | 15min | Registro de versiones semántico (v0.1.0 → v0.2.0) |

**Entregable:** Proyecto seguro, configurable por env vars, Docker optimizado.
**Tests:** ~32 tests.

---

## Fase 3 — Producto base (batch + auth + schedule)

| # | Tarea | Esfuerzo | Descripción |
|---|-------|----------|-------------|
| 3.1 | **Modo batch** | 2h | `python -m etl run URL --selectors "..." --webhook $URL` → scrape + process + export + notify en un comando |
| 3.2 | **Auth en dashboard** | 1h | Streamlit secrets `[dashboard] password = "..."`. Login simple con `st.text_input` |
| 3.3 | **Programador automático** | 4h | `python -m etl schedule --cron "0 */6 * * *"`. Usa `schedule.yml` ya existente en CI |
| 3.4 | **Data retention** | 1h | `python -m etl cleanup --days 30`. Purga `raw_data` + `processed_data` según antigüedad |

**Entregable:** Pipeline ejecutable sin intervención, dashboard protegido, datos auto-gestionados.
**Tests:** ~38 tests.

---

## Fase 4 — API + Observabilidad

| # | Tarea | Esfuerzo | Descripción |
|---|-------|----------|-------------|
| 4.1 | **API REST FastAPI** | 6h | Endpoints: `GET /data`, `GET /stats`, `POST /scrape`. Reutiliza `etl/` modules |
| 4.2 | **Export incremental** | 2h | `python -m etl export --since 2026-07-01`. Solo exporta registros nuevos |
| 4.3 | **Memory limit en dashboard** | 1h | Paginación server-side en Streamlit. Máximo 5K registros en RAM a la vez |
| 4.4 | **Health check endpoint** | 30min | `GET /health` → `{"status":"ok","db_size":"12MB","last_scrape":"..."}` |
| 4.5 | **Métricas Prometheus** | 2h | Endpoint `/metrics` con contadores: `scrape_duration_seconds`, `rows_inserted_total`, `export_count` |

**Entregable:** API REST funcional, sistema observable, métricas exportables.
**Tests:** ~48 tests.

---

## Fase 5 — Dashboard avanzado

| # | Tarea | Esfuerzo | Descripción |
|---|-------|----------|-------------|
| 5.1 | **Filtros multi-columna + búsqueda** | 3h | Sidebar con selects dinámicos. Filtro combinable por cualquier columna. Búsqueda textual |
| 5.2 | **Gráficos configurables** | 2h | Selector de columna X / Y / color. El usuario decide qué graficar |
| 5.3 | **Guardar dashboard como imagen** | 1h | Botón "📸 Exportar dashboard como PNG". Plotly soporta `to_image()` |

**Entregable:** Dashboard interactivo rico, exportable, usable por no-técnicos.
**Tests:** ~52 tests.

---

## Fase 6 — Escalabilidad (data architecture)

| # | Tarea | Esfuerzo | Descripción |
|---|-------|----------|-------------|
| 6.1 | **Migrar processed_data a columnar** | 2h | En vez de `data TEXT (JSON)`, crear columnas reales en SQLite. Consultas 10x más rápidas |
| 6.2 | **Cobertura de tests >80%** | 2h | `pytest-cov`. Añadir tests para edge cases faltantes |
| 6.3 | **CI ejecuta test runner real** | 30min | `ci.yml` corre `python run_tests.py` además de pytest |

**Entregable:** Datos consultables directamente desde SQL, sin expansión JSON.
**Tests:** ~60 tests, cobertura >80%.

---

## Mapa de dependencias

```
Fase 1 ─────────────────────────────────────────────┐
  ├─ 1.1 Tests (base para todas)                     │
  ├─ 1.2 Lint (base para calidad)                    ├──  Fase 2 ──  Fase 3 ──  Fase 4 ──  Fase 5 ──  Fase 6
  ├─ 1.3 No-dup (base para A4+A2)                    │     │            │            │            │
  ├─ 1.4 Logging (base para Q1-Q2)                   │     ├─ 2.1       ├─ 3.1       ├─ 4.1       ├─ 5.1       ├─ 6.1
  └─ 1.5 Types (base para CI)                        │     ├─ 2.2       ├─ 3.2       ├─ 4.2       ├─ 5.2       ├─ 6.2
                                                      │     ├─ 2.3       ├─ 3.3       ├─ 4.3       ├─ 5.3       └─ 6.3
                                                      │     ├─ 2.4       └─ 3.4       ├─ 4.4
                                                      │     └─ 2.5                    └─ 4.5
```

## Timeline estimado

| Fase | Tiempo | Commits | Dependencia |
|------|--------|---------|-------------|
| 1 | ~4h | 5 | Ninguna |
| 2 | ~2.5h | 5 | Fase 1 |
| 3 | ~8h | 4 | Fase 2 |
| 4 | ~11.5h | 5 | Fase 3 |
| 5 | ~6h | 3 | Fase 4 |
| 6 | ~4.5h | 3 | Fase 1 |
| **Total** | **~36.5h** | **25** | — |

---

## Criterios de aceptación globales

- ✅ `python -m pytest tests/` → 0 failures
- ✅ `ruff check .` → 0 errors
- ✅ `mypy etl/ --strict` → 0 errors
- ✅ `docker build .` → exit 0, imagen <300MB
- ✅ Dashboard accesible en `http://localhost:8501`
- ✅ `python -m etl run URL --selectors ... --webhook ...` → batch completo
- ✅ `python -m etl schedule --cron "0 */6 * * *"` → schedule persistente
- ✅ `GET /health` → 200, `GET /metrics` → 200
