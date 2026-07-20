"""Dashboard Streamlit + Plotly para DataPipeline.

Ejecutar:
    streamlit run dashboard/streamlit_app.py
    # o
    python -m etl dashboard --mode streamlit
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from etl.config import validate_db_path
from etl.process import expand_json_records

# --- Auth ---
try:
    DASHBOARD_PASSWORD = st.secrets.get("dashboard", {}).get("password")
except Exception:
    DASHBOARD_PASSWORD = None


def check_auth() -> bool:
    """Verifica autenticación. Retorna True si está autenticado o no hay password."""
    if not DASHBOARD_PASSWORD:
        return True
    if "authenticated" in st.session_state and st.session_state.authenticated:
        return True
    return False


def render_login() -> None:
    """Renderiza formulario de login."""
    st.title("🔐 DataPipeline Dashboard")
    with st.form("login_form"):
        pwd = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            if pwd == DASHBOARD_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Contraseña incorrecta")


# --- Configuración ---
st.set_page_config(
    page_title="DataPipeline Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Auth gate ---
if not check_auth():
    render_login()
    st.stop()

# --- Sidebar ---
# Dark theme CSS
st.markdown(
    """
<style>
    .main .block-container { padding-top: 1rem; max-width: 100%; }
    .stMetric { background: #1e1e1e; border-radius: 8px; padding: 12px; }
    .stMetric label { color: #a0a0a0; }
    .stMetric [data-testid="stMetricValue"] { color: #4fc3f7; }
    div[data-testid="stSidebar"] { background-color: #1a1a2e; }
</style>
""",
    unsafe_allow_html=True,
)


# --- Data loading ---
MAX_FRAME = 5000  # Máximo de filas en RAM


def get_db_path() -> str:
    """Obtiene la ruta de la DB desde session_state o variable de entorno."""
    import os

    if "db_path" not in st.session_state:
        st.session_state.db_path = os.environ.get("ETL_DB_PATH", "data/pipeline.db")
    return st.session_state.db_path


@st.cache_data
def load_data(db_path: str) -> pd.DataFrame:
    """Carga y expande datos de SQLite (máx. MAX_FRAME filas)."""
    path = Path(db_path)
    if not path.exists():
        return pd.DataFrame()

    conn = sqlite3.connect(str(path))
    try:
        df = pd.read_sql_query(f"SELECT * FROM raw_data LIMIT {MAX_FRAME}", conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()

    if df.empty:
        return df

    return expand_json_records(df, data_col="data")


def load_processed_data(db_path: str) -> pd.DataFrame:
    """Carga datos procesados de SQLite (máx. MAX_FRAME filas)."""
    path = Path(db_path)
    if not path.exists():
        return pd.DataFrame()

    conn = sqlite3.connect(str(path))
    try:
        df = pd.read_sql_query(f"SELECT * FROM processed_data LIMIT {MAX_FRAME}", conn)
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()

    if df.empty:
        return df

    return expand_json_records(df, data_col="data")


# --- Sidebar ---
st.sidebar.title("⚙ Configuración")
db_path_input = st.sidebar.text_input(
    "Ruta de la base de datos",
    value=get_db_path(),
    key="db_path_input",
)
st.session_state.db_path = db_path_input

# Validate path
try:
    validate_db_path(st.session_state.db_path)
except ValueError as e:
    st.sidebar.error(f"Ruta inválida: {e}")

# Data source selector
data_source = st.sidebar.radio(
    "Fuente de datos",
    ["Raw (scraped)", "Processed"],
    index=0,
)

# Load data
db_path = get_db_path()
df = load_data(db_path) if data_source == "Raw (scraped)" else load_processed_data(db_path)

if df.empty:
    st.warning("⚠ No hay datos disponibles. Ejecuta primero el pipeline ETL:")
    st.code('python -m etl scrape <url> --selectors "h2.title" ".price"\npython -m etl process', language="bash")
    st.stop()

# Memory limit warning
try:
    conn = sqlite3.connect(Path(db_path))
    actual_total = conn.execute("SELECT COUNT(*) FROM raw_data").fetchone()[0]
    conn.close()
    if actual_total > MAX_FRAME:
        st.info(f"ℹ Mostrando {MAX_FRAME:,} de {actual_total:,} registros. Usa filtros para refinar.")
except Exception:
    pass

# --- Filters ---
st.sidebar.markdown("---")
st.sidebar.markdown("### 🔍 Filtros")

# Text search
search_query = st.sidebar.text_input("🔎 Búsqueda textual", placeholder="Escribe para filtrar...")

# Dynamic multi-column filters
non_meta_cols = [c for c in df.columns if not c.startswith("_")]
string_cols = df.select_dtypes(include=["object", "string"]).columns.tolist()
string_cols = [c for c in string_cols if c in non_meta_cols][:6]  # limit to 6

col_filters: dict[str, str | None] = {}
for col_name in string_cols:
    unique_vals = sorted(df[col_name].dropna().unique().tolist())
    if len(unique_vals) > 1 and len(unique_vals) <= 100:
        opts = ["All"] + [str(v) for v in unique_vals[:50]]
        selected = st.sidebar.selectbox(f"{col_name}", opts, key=f"filt_{col_name}")
        col_filters[col_name] = None if selected == "All" else selected

# Apply filters
for col, val in col_filters.items():
    if val is not None:
        df = df[df[col].astype(str) == val]

if search_query:
    mask = df.astype(str).apply(lambda row: row.str.contains(search_query, case=False, na=False).any(), axis=1)
    df = df[mask]

# --- Main content ---
st.title("📊 DataPipeline Dashboard")

# --- Metrics ---
st.markdown("### 📈 Resumen")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("📋 Total registros", len(df))

with col2:
    domain_count = df["_source_domain"].nunique() if "_source_domain" in df.columns else 0
    st.metric("🌐 Dominios", domain_count)

with col3:
    url_count = df["_source_url"].nunique() if "_source_url" in df.columns else 0
    st.metric("🔗 URLs", url_count)

with col4:
    if "_scraped_at" in df.columns and not df["_scraped_at"].empty:
        dates = pd.to_datetime(df["_scraped_at"], errors="coerce").dropna()
        date_range = f"{dates.min().date()} → {dates.max().date()}" if not dates.empty else "N/A"
    else:
        date_range = "N/A"
    st.metric("📅 Rango fechas", date_range)

st.markdown("---")

# --- Configurable Charts ---
st.markdown("### 📈 Gráficos configurables")

with st.expander("⚙ Configurar gráfico", expanded=False):
    chart_type = st.selectbox(
        "Tipo de gráfico",
        ["Barra", "Línea", "Dispersión", "Histograma", "Pastel", "Box"],
        key="chart_type",
    )
    all_cols = df.columns.tolist()
    x_col = st.selectbox("Eje X / Categoría", all_cols, key="chart_x")
    y_hint = "Eje Y (opcional)" if chart_type in ("Histograma", "Pastel") else "Eje Y"
    y_col = st.selectbox(y_hint, [None] + all_cols, key="chart_y")
    color_col = st.selectbox("Color / Agrupar por", [None] + all_cols, key="chart_color")

# Build the chart
fig = None
if chart_type == "Barra" and y_col and x_col in df.columns:
    grp = df.groupby(x_col)[y_col].sum().reset_index().sort_values(y_col, ascending=False).head(30)
    fig = px.bar(
        grp,
        x=x_col,
        y=y_col,
        color=color_col if color_col else None,
        color_continuous_scale="blues" if not color_col else None,
    )
elif chart_type == "Línea" and y_col and x_col in df.columns:
    grp = df.groupby(x_col)[y_col].mean().reset_index()
    fig = px.line(grp, x=x_col, y=y_col, markers=True, color=color_col if color_col else None)
elif chart_type == "Dispersión" and y_col and x_col in df.columns:
    fig = px.scatter(df, x=x_col, y=y_col, color=color_col if color_col else None, opacity=0.6)
elif chart_type == "Histograma":
    fig = px.histogram(df, x=x_col, color=color_col if color_col else None, nbins=30)
elif chart_type == "Pastel" and x_col in df.columns:
    counts = df[x_col].value_counts().head(20).reset_index()
    counts.columns = [x_col, "count"]
    fig = px.pie(counts, names=x_col, values="count", hole=0.4, color_discrete_sequence=px.colors.qualitative.Set2)
elif chart_type == "Box" and y_col and x_col in df.columns:
    fig = px.box(df, x=x_col, y=y_col, color=color_col if color_col else None)

if fig:
    fig.update_layout(template="plotly_dark", height=400, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

# Retained static charts (domain + timeline) as a compact row
st.markdown("#### 📊 Vistas rápidas")
qc1, qc2 = st.columns(2)
with qc1:
    if "_source_domain" in df.columns:
        dc = df["_source_domain"].value_counts().reset_index()
        dc.columns = ["domain", "count"]
        st.plotly_chart(
            px.pie(
                dc, names="domain", values="count", hole=0.4, color_discrete_sequence=px.colors.qualitative.Set2
            ).update_layout(template="plotly_dark", height=280, margin=dict(l=5, r=5, t=5, b=5)),
            use_container_width=True,
        )
with qc2:
    if "_scraped_at" in df.columns:
        dates = pd.to_datetime(df["_scraped_at"], errors="coerce").dropna()
        if not dates.empty:
            daily = dates.dt.date.value_counts().sort_index().reset_index()
            daily.columns = ["date", "count"]
            st.plotly_chart(
                px.line(daily, x="date", y="count", markers=True, color_discrete_sequence=["#4fc3f7"]).update_layout(
                    template="plotly_dark", height=280, margin=dict(l=5, r=5, t=5, b=5)
                ),
                use_container_width=True,
            )

# --- Data Table ---
st.markdown("---")
st.markdown("### 📋 Datos")

# Pagination
PAGE_SIZE = 20
total_pages = max(1, (len(df) - 1) // PAGE_SIZE + 1)
page = st.number_input("Página", min_value=1, max_value=total_pages, value=1, step=1)
start = (page - 1) * PAGE_SIZE
end = min(start + PAGE_SIZE, len(df))

st.caption(f"Mostrando {start + 1}-{end} de {len(df)} registros")
st.dataframe(df.iloc[start:end], use_container_width=True, height=400)

# --- Export ---
st.markdown("---")
st.markdown("### 💾 Exportar")

col_e1, col_e2, col_e3 = st.columns(3)

with col_e1:
    csv_data = df.to_csv(index=False)
    st.download_button(
        label="📥 Descargar CSV",
        data=csv_data,
        file_name="datapipeline_export.csv",
        mime="text/csv",
    )

with col_e2:
    json_data = df.to_json(orient="records", indent=2)
    st.download_button(
        label="📥 Descargar JSON",
        data=json_data,
        file_name="datapipeline_export.json",
        mime="application/json",
    )

with col_e3:
    try:
        import plotly.io as pio

        # Re-create figure for PNG capture
        if fig:
            png_bytes = pio.to_image(fig, format="png", width=1200, height=600, scale=2)
            st.download_button(
                label="📸 Exportar gráfico como PNG",
                data=png_bytes,
                file_name="datapipeline_chart.png",
                mime="image/png",
            )
    except Exception:
        pass

# --- Footer ---
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666;'>DataPipeline v0.1.0 | Powered by Streamlit + Plotly</div>",
    unsafe_allow_html=True,
)
