# Plan — Mejoras DataPipeline

## Resumen
5 mejoras post-MVP para el pipeline ETL. Cada una es independiente y desplegable por separado.

---

## 1. Multi-target Scraping con concurrencia

**Estado:** Actualmente URLs se procesan con `asyncio.gather` pero sin control de concurrencia real.

**Cambios:**
- `ScrapeConfig` → añadir `max_concurrent: int = 10`
- `run_scrape()` → usar `asyncio.Semaphore` para limitar concurrencia
- CLI: `python -m etl scrape --concurrency 10 <urls> --selectors ...`
- Tests: verificar que se respeta el límite de concurrencia

**Archivos:** `etl/config.py`, `etl/scrape.py`, `etl/__main__.py`, `tests/test_scrape.py`

---

## 2. Deduplicación incremental

**Estado:** `scrape.py` inserta siempre filas nuevas sin verificar duplicados.

**Cambios:**
- `save_to_sqlite()` → antes de insertar, verificar hash de contenido contra tabla `raw_data`
- Añadir columna `content_hash TEXT UNIQUE` en `raw_data`
- Opcional: flag `--incremental` en CLI, por defecto `true`
- Log: "✓ 3/10 URLs nuevas, 7 saltadas (ya existentes)"

**Archivos:** `etl/scrape.py`, `etl/__main__.py`, `etl/config.py`

---

## 3. Webhook alerts

**Nuevo módulo:** `etl/notify.py`

**Funcionalidad:**
- Disparar webhook (Slack/Discord/HTTP genérico) cuando:
  - Scraping encuentra cambios significativos (>X% datos nuevos)
  - Errores recurrentes (N+ fallos seguidos)
  - Nuevos dominios detectados
- Configurable vía CLI/env vars: `--webhook-url`, `--webhook-threshold`
- Payload JSON con resumen del cambio

**Archivos nuevos:** `etl/notify.py`
**Archivos modificar:** `etl/__main__.py`, `etl/scrape.py`, `etl/config.py`
**Tests:** `tests/test_notify.py`

---

## 4. Export Parquet

**Estado:** Solo CSV/JSON con stdlib.

**Cambios:**
- Añadir dependencia `pyarrow` o usar `pandas.DataFrame.to_parquet()` (ya tenemos pandas)
- CLI: `python -m etl export --format parquet|csv|json|both`
- `etl/export.py` → añadir `export_parquet()` con pandas

**Archivos:** `etl/export.py`, `etl/__main__.py`
**Dependencias:** `pyarrow` en `requirements.txt`

---

## 5. pandas avanzado — transformaciones

**Estado:** pandas se usa solo para limpieza básica y carga.

**Mejoras posibles:**
- `--transform` flag que acepta expresiones pandas eval (ej: `price * 1.21` para IVA)
- Pipeline de transforms: `process --transform "price=price*1.21" --transform "name=name.str.upper()"`
- Detección automática de tipos de datos (numéricos vs strings)
- Estadísticas descriptivas post-proceso (`process --stats`)
- `--group-by` para agregaciones básicas

**Archivos:** `etl/process.py`, `etl/__main__.py`, `etl/config.py`

---

## Dependencias entre mejoras

```
1. Multi-target     → independiente
2. Dedup incremental → independiente
3. Webhook alerts   → ideal después de 1 y 2 (alertas más útiles con concurrencia + dedup)
4. Export Parquet   → independiente
5. pandas avanzado  → independiente
```

Todas son **paralelizables** excepto 3→recomendado después de 1+2.

## Archivos afectados (por frecuencia)

| Archivo | 1 | 2 | 3 | 4 | 5 |
|---------|---|---|---|---|---|
| `etl/config.py` | ✓ | ✓ | ✓ |   | ✓ |
| `etl/scrape.py` | ✓ | ✓ | ✓ |   |   |
| `etl/process.py` |   |   |   |   | ✓ |
| `etl/export.py` |   |   |   | ✓ |   |
| `etl/notify.py` |   |   | nuevo |   |   |
| `etl/__main__.py` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `tests/*` | ✓ | ✓ | ✓ | ✓ | ✓ |
