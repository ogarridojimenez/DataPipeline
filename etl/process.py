"""Transformaciones avanzadas con pandas: stats, group-by, agregaciones."""

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


def compute_summary(df: pd.DataFrame) -> dict:
    """Calcula estadísticas resumen del DataFrame."""
    if df.empty:
        return {}

    non_meta = [c for c in df.columns if not c.startswith("_")]
    num_cols = df[non_meta].select_dtypes(include=["number"]).columns.tolist()
    cat_cols = df[non_meta].select_dtypes(include=["object"]).columns.tolist()

    summary: dict = {
        "total_records": len(df),
        "numeric_columns": len(num_cols),
        "categorical_columns": len(cat_cols),
    }

    if num_cols:
        summary["numeric_stats"] = {
            col: {
                "mean": round(df[col].mean(), 2),
                "median": round(df[col].median(), 2),
                "std": round(df[col].std(), 2),
                "min": round(df[col].min(), 2),
                "max": round(df[col].max(), 2),
            }
            for col in num_cols
        }

    if cat_cols:
        summary["categorical_top"] = {
            col: df[col].value_counts().head(3).to_dict()
            for col in cat_cols
        }

    # Dominio stats
    if "_source_domain" in df.columns:
        summary["top_domains"] = df["_source_domain"].value_counts().head(5).to_dict()

    return summary


def group_by_domain(df: pd.DataFrame) -> pd.DataFrame:
    """Agrupa por dominio y calcula métricas agregadas."""
    if df.empty or "_source_domain" not in df.columns:
        return pd.DataFrame()

    non_meta = [c for c in df.columns if not c.startswith("_")]
    num_cols = df[non_meta].select_dtypes(include=["number"]).columns.tolist()

    if not num_cols:
        # Si no hay numéricas, contar registros
        return df.groupby("_source_domain").size().reset_index(name="count")

    aggs: dict[str, str] = {col: ["mean", "min", "max", "count"] for col in num_cols}
    result = df.groupby("_source_domain").agg(aggs)
    result.columns = [f"{col}_{agg}" for col, agg in result.columns]
    return result.reset_index()


def pipeline_pipe(df: pd.DataFrame, steps: list[dict]) -> pd.DataFrame:
    """Ejecuta una serie de pipes de transformación configurables.

    Cada step es un dict con:
      - type: "filter" | "sort" | "top_n" | "add_rank" | "normalize"
      - params: dict con los parámetros de la operación
    """
    result = df.copy()
    for step in steps:
        t = step["type"]
        p = step.get("params", {})

        if t == "filter":
            col = p.get("column")
            op = p.get("op", "eq")
            val = p.get("value")
            if col in result.columns:
                if op == "eq":
                    result = result[result[col] == val]
                elif op == "gt":
                    result = result[result[col] > val]
                elif op == "gte":
                    result = result[result[col] >= val]
                elif op == "lt":
                    result = result[result[col] < val]
                elif op == "lte":
                    result = result[result[col] <= val]
                elif op == "ne":
                    result = result[result[col] != val]
                elif op == "contains":
                    result = result[result[col].astype(str).str.contains(str(val), na=False)]
        elif t == "sort":
            col = p.get("column")
            asc = p.get("ascending", True)
            if col in result.columns:
                result = result.sort_values(by=col, ascending=asc)
        elif t == "top_n":
            col = p.get("column")
            n = p.get("n", 10)
            if col in result.columns:
                result = result.nlargest(n, col)
        elif t == "add_rank":
            col = p.get("column")
            name = p.get("name", "rank")
            asc = p.get("ascending", True)
            if col in result.columns:
                result[name] = result[col].rank(ascending=asc)
        elif t == "normalize":
            col = p.get("column")
            name = p.get("name", None) or f"{col}_norm"
            method = p.get("method", "minmax")  # minmax | zscore
            if col in result.columns:
                if method == "minmax":
                    mn, mx = result[col].min(), result[col].max()
                    if mx != mn:
                        result[name] = (result[col] - mn) / (mx - mn)
                    else:
                        result[name] = 0
                elif method == "zscore":
                    mean, std = result[col].mean(), result[col].std()
                    result[name] = (result[col] - mean) / std if std > 0 else 0

    return result


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


def run_process(db_path, config: ProcessConfig, verbose: bool = True) -> None:
    """Ejecuta el pipeline de procesamiento completo."""
    if verbose:
        print(f"⚙ Procesando datos de {db_path}...")
    df = load_raw_data(db_path)

    if df.empty:
        print("⚠ No hay datos para procesar")
        return

    cleaned = clean_data(df, config)

    # Resumen avanzado
    summary = compute_summary(cleaned)
    if verbose and summary:
        print(f"  📊 Registros: {summary['total_records']}")
        print(f"  🔢 Columnas numéricas: {summary.get('numeric_columns', 0)}")
        print(f"  📝 Columnas categóricas: {summary.get('categorical_columns', 0)}")
        if "top_domains" in summary:
            print(f"  🌐 Top dominios: {', '.join(summary['top_domains'].keys())}")
        if summary.get("numeric_stats"):
            for col, stats in summary["numeric_stats"].items():
                print(f"  📈 {col}: media={stats['mean']}, min={stats['min']}, max={stats['max']}")

    # Group by dominio
    gb = group_by_domain(cleaned)
    if verbose and not gb.empty:
        print(f"  🔗 Agrupación por dominio: {len(gb)} grupos")

    save_processed(cleaned, db_path)
    if verbose:
        print(f"✓ Procesamiento completo: {len(cleaned)} registros limpios")
