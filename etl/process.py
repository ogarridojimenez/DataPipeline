"""Fase de procesamiento: limpieza, deduplicación, outliers (stdlib + numpy)."""

from __future__ import annotations

import json
import logging
import math
import sqlite3
from pathlib import Path
from statistics import mean, stdev

from etl.config import ProcessConfig

logger = logging.getLogger("etl.process")


def load_raw_data(db_path: Path) -> list[dict]:
    """Carga y expande datos raw desde SQLite."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT source_url, source_domain, data, scraped_at FROM raw_data")
    rows = cursor.fetchall()
    conn.close()

    records = []
    for url, domain, data_json, scraped_at in rows:
        items = json.loads(data_json)
        for item in items:
            item["_source_url"] = url
            item["_source_domain"] = domain
            item["_scraped_at"] = scraped_at
            records.append(item)
    return records


def _try_numeric(val: str) -> float | str:
    """Intenta convertir string a número."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return val


def clean_data(records: list[dict], config: ProcessConfig) -> list[dict]:
    """Limpieza: dedup, nulls, normalización, outliers."""
    if not records:
        return records

    initial_len = len(records)

    # 1. Eliminar duplicados exactos
    seen = set()
    unique = []
    for r in records:
        key = tuple(sorted((k, v) for k, v in r.items() if not k.startswith("_")))
        if key not in seen:
            seen.add(key)
            unique.append(r)
    dupes_removed = initial_len - len(unique)
    if dupes_removed:
        logger.info("Duplicados eliminados: %d", dupes_removed)

    # 2. Rellenar/eliminar nulls y strings vacíos
    cleaned = []
    for r in unique:
        has_empty = any(v == "" or v is None for k, v in r.items() if not k.startswith("_"))
        if has_empty:
            if config.fill_null_strategy == "drop":
                continue
            elif config.fill_null_strategy == "fill":
                r = {k: ("" if (v == "" or v is None) and not k.startswith("_") else v) for k, v in r.items()}
        cleaned.append(r)

    # 3. Normalizar strings: strip
    for r in cleaned:
        for k, v in r.items():
            if isinstance(v, str) and not k.startswith("_"):
                r[k] = v.strip()

    # 4. Detectar outliers por columna numérica
    numeric_cols = set()
    for r in cleaned:
        for k, v in r.items():
            if not k.startswith("_") and isinstance(v, str):
                converted = _try_numeric(v)
                if isinstance(converted, float):
                    numeric_cols.add(k)

    # Convertir valores numéricos
    for r in cleaned:
        for col in numeric_cols:
            if col in r and isinstance(r[col], str):
                r[col] = _try_numeric(r[col])

    # Marcar outliers
    for col in numeric_cols:
        values = [r[col] for r in cleaned if col in r and isinstance(r[col], (int, float))]
        if len(values) < 3:
            continue
        mu = mean(values)
        sigma = stdev(values)
        if sigma > 0:
            for r in cleaned:
                if col in r and isinstance(r[col], (int, float)):
                    is_outlier = abs(r[col] - mu) > config.outlier_std_threshold * sigma
                    r[f"{col}_is_outlier"] = is_outlier
                    if is_outlier:
                        logger.info("Outlier en '%s': %s", col, r[col])

    logger.info("Procesamiento completo: %d filas (de %d)", len(cleaned), initial_len)
    return cleaned


def save_processed(records: list[dict], db_path: Path) -> None:
    """Guarda datos procesados en SQLite."""
    if not records:
        logger.warning("Datos vacíos, nada que guardar")
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Recopilar todas las columnas
    all_cols = set()
    for r in records:
        all_cols.update(r.keys())

    cols = sorted(all_cols)
    col_defs = ", ".join(f"{c} TEXT" for c in cols)
    cursor.execute(f"DROP TABLE IF EXISTS processed_data")
    cursor.execute(f"CREATE TABLE processed_data ({col_defs})")

    for r in records:
        placeholders = ", ".join("?" * len(cols))
        values = [json.dumps(r.get(c)) if isinstance(r.get(c), (list, dict)) else str(r.get(c, "")) for c in cols]
        cursor.execute(f"INSERT INTO processed_data ({', '.join(cols)}) VALUES ({placeholders})", values)

    conn.commit()
    conn.close()
    logger.info("Datos procesados guardados en %s (tabla: processed_data)", db_path)


def run_process(db_path: Path, config: ProcessConfig) -> None:
    """Ejecuta el pipeline de procesamiento."""
    print(f"Cargando datos de {db_path}...")
    records = load_raw_data(db_path)

    if not records:
        print("⚠ No hay datos para procesar. Ejecuta 'scrape' primero.")
        return

    print(f"Datos raw: {len(records)} filas")
    records = clean_data(records, config)
    save_processed(records, db_path)
    print(f"✓ Procesamiento completo: {len(records)} filas limpias guardadas")
