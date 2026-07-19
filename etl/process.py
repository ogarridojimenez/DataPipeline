"""Fase de procesamiento: pandas data cleaning + detección outliers."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd

from etl.config import ProcessConfig


def load_raw_data(db_path) -> pd.DataFrame:
    """Carga datos raw de SQLite y expande JSON anidado."""
    conn = sqlite3.connect(str(db_path))
    df = pd.read_sql_query("SELECT * FROM raw_data", conn)
    conn.close()

    if df.empty:
        return df

    # Expandir JSON anidado
    records = []
    for _, row in df.iterrows():
        items = json.loads(row["data"])
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    item["_source_url"] = row.get("source_url", "")
                    item["_source_domain"] = row.get("source_domain", "")
                    item["_scraped_at"] = row.get("scraped_at", "")
                    records.append(item)
        elif isinstance(items, dict):
            items["_source_url"] = row.get("source_url", "")
            items["_source_domain"] = row.get("source_domain", "")
            items["_scraped_at"] = row.get("scraped_at", "")
            records.append(items)

    return pd.DataFrame(records)


def clean_data(df: pd.DataFrame, config: ProcessConfig) -> pd.DataFrame:
    """Limpieza completa: dedup, nulls, tipos, outliers."""
    if df.empty:
        return df

    initial = len(df)

    # 1. Eliminar duplicados exactos
    df = df.drop_duplicates()
    dups_removed = initial - len(df)
    if dups_removed:
        print(f"  ✓ Duplicados eliminados: {dups_removed}")

    # 2. Normalizar strings (strip whitespace)
    str_cols = df.select_dtypes(include=["object"]).columns
    for col in str_cols:
        df[col] = df[col].str.strip() if df[col].dtype == "object" else df[col]

    # 3. Manejar valores vacíos/nulos
    non_meta = [c for c in df.columns if not c.startswith("_")]
    if config.fill_null_strategy == "drop":
        before = len(df)
        df = df.dropna(subset=non_meta, how="all")
        df = df[~(df[non_meta].eq("").all(axis=1))]
        nulls_removed = before - len(df)
        if nulls_removed:
            print(f"  ✓ Filas vacías eliminadas: {nulls_removed}")
    elif config.fill_null_strategy == "fill":
        df[non_meta] = df[non_meta].fillna("")
    elif config.fill_null_strategy == "mean":
        num_cols = df[non_meta].select_dtypes(include=["number"]).columns
        df[num_cols] = df[num_cols].fillna(df[num_cols].mean())
    elif config.fill_null_strategy == "median":
        num_cols = df[non_meta].select_dtypes(include=["number"]).columns
        df[num_cols] = df[num_cols].fillna(df[num_cols].median())

    # 4. Detectar outliers numéricos
    num_cols = df.select_dtypes(include=["number"]).columns
    num_cols = [c for c in num_cols if not c.startswith("_")]
    if num_cols and config.outlier_std_threshold > 0:
        for col in num_cols:
            mean = df[col].mean()
            std = df[col].std()
            if std > 0:
                outliers = (df[col] - mean).abs() > (config.outlier_std_threshold * std)
                n_outliers = outliers.sum()
                if n_outliers:
                    print(f"  ⚠ Outliers en '{col}': {n_outliers} (> {config.outlier_std_threshold}σ)")

    print(f"  ✓ Limpieza: {initial} → {len(df)} registros")
    return df


def save_processed(df: pd.DataFrame, db_path) -> None:
    """Guarda DataFrame procesado en SQLite."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS processed_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_url TEXT,
            source_domain TEXT,
            data TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Convertir cada fila a JSON
    for _, row in df.iterrows():
        record = {}
        for k, v in row.items():
            if not k.startswith("_"):
                record[k] = v
        source_url = row.get("_source_url", "")
        source_domain = row.get("_source_domain", "")
        scraped_at = row.get("_scraped_at", "")

        cursor.execute(
            "INSERT INTO processed_data (source_url, source_domain, data, scraped_at) VALUES (?, ?, ?, ?)",
            (source_url, source_domain, json.dumps(record), scraped_at),
        )

    conn.commit()
    conn.close()


def run_process(db_path, config: ProcessConfig) -> None:
    """Ejecuta el pipeline de procesamiento completo."""
    print(f"⚙ Procesando datos de {db_path}...")
    df = load_raw_data(db_path)

    if df.empty:
        print("⚠ No hay datos para procesar")
        return

    cleaned = clean_data(df, config)
    save_processed(cleaned, db_path)
    print(f"✓ Procesamiento completo: {len(cleaned)} registros limpios")
