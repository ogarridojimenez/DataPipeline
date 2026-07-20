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

# Domain filter
domains = ["All"] + sorted(df["_source_domain"].unique().tolist()) if "_source_domain" in df.columns else ["All"]
selected_domain = st.sidebar.selectbox("Dominio", domains, index=0)

# Apply domain filter
if selected_domain != "All" and "_source_domain" in df.columns:
    df = df[df["_source_domain"] == selected_domain]

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

# --- Charts ---
# Identify columns (exclude metadata)
meta_cols = [c for c in df.columns if c.startswith("_")]
data_cols = [c for c in df.columns if not c.startswith("_")]

if not data_cols:
    st.info("No hay columnas de datos para graficar.")
else:
    chart_col1, chart_col2 = st.columns(2)

    # --- Bar Chart: top items ---
    with chart_col1:
        st.markdown("#### 📊 Top Elementos")
        # Find the first text column for grouping
        text_col = data_cols[0]
        if text_col in df.columns:
            counts = df[text_col].value_counts().head(10).reset_index()
            counts.columns = [text_col, "count"]
            fig_bar = px.bar(
                counts,
                x="count",
                y=text_col,
                orientation="h",
                color="count",
                color_continuous_scale="blues",
            )
            fig_bar.update_layout(
                template="plotly_dark",
                height=400,
                showlegend=False,
                margin=dict(l=10, r=10, t=10, b=10),
            )
            st.plotly_chart(fig_bar, use_container_width=True)

    # --- Doughnut Chart: domain distribution ---
    with chart_col2:
        st.markdown("#### 🍩 Distribución por Dominio")
        if "_source_domain" in df.columns:
            domain_counts = df["_source_domain"].value_counts().reset_index()
            domain_counts.columns = ["domain", "count"]
            fig_donut = px.pie(
                domain_counts,
                names="domain",
                values="count",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            fig_donut.update_layout(
                template="plotly_dark",
                height=400,
                showlegend=True,
                margin=dict(l=10, r=10, t=10, b=10),
            )
            st.plotly_chart(fig_donut, use_container_width=True)

    # --- Line Chart: records over time ---
    if "_scraped_at" in df.columns:
        st.markdown("#### 📈 Registros por Día")
        dates = pd.to_datetime(df["_scraped_at"], errors="coerce").dropna()
        if not dates.empty:
            daily = dates.dt.date.value_counts().sort_index().reset_index()
            daily.columns = ["date", "count"]
            fig_line = px.line(
                daily,
                x="date",
                y="count",
                markers=True,
                color_discrete_sequence=["#4fc3f7"],
            )
            fig_line.update_layout(
                template="plotly_dark",
                height=300,
                showlegend=False,
                margin=dict(l=10, r=10, t=10, b=10),
                xaxis_title="Fecha",
                yaxis_title="Registros",
            )
            st.plotly_chart(fig_line, use_container_width=True)

    # --- Multi-column charts ---
    num_cols = df.select_dtypes(include=["number"]).columns.tolist()
    num_cols = [c for c in num_cols if not c.startswith("_")]

    if len(num_cols) >= 2:
        st.markdown("#### 🔬 Distribución Numérica")
        cols = st.columns(min(len(num_cols), 4))
        for i, col_name in enumerate(num_cols[:4]):
            with cols[i]:
                fig_hist = px.histogram(
                    df,
                    x=col_name,
                    nbins=20,
                    color_discrete_sequence=["#81c784"],
                )
                fig_hist.update_layout(
                    template="plotly_dark",
                    height=250,
                    showlegend=False,
                    margin=dict(l=5, r=5, t=5, b=5),
                )
                st.plotly_chart(fig_hist, use_container_width=True)

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

col_e1, col_e2 = st.columns(2)

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

# --- Footer ---
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666;'>DataPipeline v0.1.0 | Powered by Streamlit + Plotly</div>",
    unsafe_allow_html=True,
)
