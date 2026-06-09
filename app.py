"""
app.py
──────
Lumina v2 — Streamlit entry point (thin shell).

Responsibilities:
  • Page config + CSS injection (must be first Streamlit call)
  • Sidebar: API key, file upload, sheet selector, dataset overview,
             example prompts, export/clear buttons
  • On file upload: run insight_engine + graph_engine and store in session state

All Q&A pipeline logic lives in pages/1_Chat.py.
"""

from __future__ import annotations

import hashlib
import html
import io
from pathlib import Path

from dotenv import load_dotenv

_APP_DIR = Path(__file__).resolve().parent
load_dotenv(_APP_DIR / ".env")

import streamlit as st

from ui_theme import CSS_BLOCK
from state_manager import clear_data_state, init_state, resolve_api_key
from excel_processor import build_schema_description, coerce_dtypes, get_sample_rows, load_excel
from demo_data import get_demo_workbook
from export_utils import export_chat_markdown, export_results_to_xlsx

# ─────────────────────────────────────────────────────────────────────────────
# Page config — must be the FIRST Streamlit call
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Lumina",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# CSS — injected from ui_theme single source of truth
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(CSS_BLOCK, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Session state init
# ─────────────────────────────────────────────────────────────────────────────
init_state()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_file_into_session(file_obj, file_name: str, fingerprint: str | None = None) -> bool:
    """
    Load a file object into session state.
    Triggers insight_engine and graph_engine.
    Returns True on success.
    """
    try:
        sheets = load_excel(file_obj)
        first = list(sheets.keys())[0]
        df = coerce_dtypes(sheets[first])

        clear_data_state()
        st.session_state.all_sheets = sheets
        st.session_state.file_name = file_name
        st.session_state.file_fingerprint = fingerprint
        st.session_state.df = df
        st.session_state.sheet_name = first
        st.session_state.schema_desc = build_schema_description(df, first)
        st.session_state.sample_rows = get_sample_rows(df)

        # Auto-profile (insight dashboard)
        try:
            from insight_engine import profile_dataframe
            st.session_state.profile = profile_dataframe(df, file_name, first)
        except Exception:
            pass

        # Register in graph DB (cross-session)
        try:
            from graph_engine import register_file
            st.session_state.graph_meta = register_file(file_name, df, first)
        except Exception:
            pass

        return True
    except Exception as exc:
        st.error(f"Failed to load file: {exc}")
        return False


def _load_demo_into_session() -> None:
    sheets = get_demo_workbook()
    first = list(sheets.keys())[0]
    df = coerce_dtypes(sheets[first])

    clear_data_state()
    st.session_state.all_sheets = sheets
    st.session_state.file_name = "demo_sales_workbook.xlsx"
    st.session_state.file_fingerprint = "demo_sales_workbook_v1"
    st.session_state.df = df
    st.session_state.sheet_name = first
    st.session_state.schema_desc = build_schema_description(df, first)
    st.session_state.sample_rows = get_sample_rows(df)

    try:
        from insight_engine import profile_dataframe
        st.session_state.profile = profile_dataframe(df, "demo_sales_workbook.xlsx", first)
    except Exception:
        pass

    try:
        from graph_engine import register_file
        st.session_state.graph_meta = register_file("demo_sales_workbook.xlsx", df, first)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-wordmark">Lumina</div>', unsafe_allow_html=True)

    # API key resolution
    env_key = resolve_api_key()
    if not env_key:
        typed = (st.text_input(
            "Gemini API key",
            type="password",
            placeholder="Or paste here if not using .env",
            help="Prefer GEMINI_API_KEY in a .env file next to app.py.",
            key="_api_key_input",
        ) or "").strip()
        st.session_state.api_key = typed
    else:
        st.session_state.api_key = env_key

    if not resolve_api_key():
        st.warning("Enter a Gemini API key to use the chat feature.")

    st.markdown("---")

    st.markdown('<div class="sidebar-section-label">WORKSPACE</div>', unsafe_allow_html=True)

    # Demo + upload
    if st.button("Load sample data", use_container_width=True, help="Load demo sales data (no upload needed)"):
        with st.spinner("Loading demo data..."):
            _load_demo_into_session()
        st.rerun()

    uploaded = st.file_uploader(
        "Upload your Excel or CSV file",
        type=["xlsx", "xls", "csv"],
        help="Supports .xlsx, .xls, and .csv",
    )

    if uploaded is not None:
        upload_bytes = uploaded.getvalue()
        upload_fingerprint = hashlib.sha256(upload_bytes).hexdigest()
    else:
        upload_fingerprint = None

    if uploaded is not None and upload_fingerprint != st.session_state.file_fingerprint:
        with st.spinner("Loading file..."):
            ok = _load_file_into_session(uploaded, uploaded.name, upload_fingerprint)
        if ok:
            st.success(f"Loaded **{uploaded.name}**")
            st.rerun()

    # Sheet selector (multi-sheet workbooks)
    if len(st.session_state.all_sheets) > 1:
        opts = list(st.session_state.all_sheets.keys())
        idx = opts.index(st.session_state.sheet_name) if st.session_state.sheet_name in opts else 0
        chosen = st.selectbox("Sheet", opts, index=idx, key="_sheet_sel")
        if chosen != st.session_state.sheet_name:
            df = coerce_dtypes(st.session_state.all_sheets[chosen])
            st.session_state.df = df
            st.session_state.sheet_name = chosen
            st.session_state.schema_desc = build_schema_description(df, chosen)
            st.session_state.sample_rows = get_sample_rows(df)
            st.session_state.chat_history = []
            st.session_state.predictions_text = None
            st.session_state.causes_text = None
            st.session_state.predictions_file = None
            st.session_state.predictions_sheet = None
            try:
                from insight_engine import profile_dataframe
                st.session_state.profile = profile_dataframe(df, st.session_state.file_name or "", chosen)
            except Exception:
                pass
            try:
                from graph_engine import register_file
                st.session_state.graph_meta = register_file(
                    st.session_state.file_name or "", df, chosen
                )
            except Exception:
                pass
            st.rerun()

    # Dataset metrics
    if st.session_state.df is not None:
        adf = st.session_state.df
        st.markdown("---")
        st.markdown("**Dataset Overview**")
        ca, cb = st.columns(2)
        ca.metric("Rows", f"{len(adf):,}")
        cb.metric("Columns", adf.shape[1])

        with st.expander("Schema", expanded=False):
            st.markdown(
                f'<div class="schema-box">{html.escape(st.session_state.schema_desc)}</div>',
                unsafe_allow_html=True,
            )
        with st.expander("Preview (first 5 rows)", expanded=False):
            st.dataframe(adf.head(), use_container_width=True)

    # Example prompts
    st.markdown("---")
    st.markdown('<div class="sidebar-section-label">NAVIGATION</div>', unsafe_allow_html=True)
    st.markdown("**Example prompts**")
    for p in [
        "What are the column names and types?",
        "Show the top 5 rows by the first numeric column.",
        "What is the average of each numeric column?",
        "How many missing values are in each column?",
        "Plot a bar chart of the top 10 categories.",
        "Show a correlation heatmap of numeric columns.",
        "Give me a full summary statistics table.",
    ]:
        if st.button(p, key=f"ex_{hash(p)}", use_container_width=True):
            st.session_state["_prefill"] = p
            st.switch_page("pages/1_Chat.py")

    # Export + clear
    st.markdown("---")
    hist = st.session_state.chat_history
    col_a, col_b = st.columns(2)
    with col_a:
        st.download_button(
            label="Export transcript",
            data=export_chat_markdown(hist, st.session_state.file_name) if hist else "# (empty)\n",
            file_name="lumina_transcript.md",
            mime="text/markdown",
            use_container_width=True,
            disabled=not hist,
            key="dl_chat_md",
        )
    with col_b:
        xlsx_bytes = export_results_to_xlsx(hist) if hist else b""
        st.download_button(
            label="Export results",
            data=xlsx_bytes if xlsx_bytes else b"",
            file_name="lumina_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            disabled=not hist,
            key="dl_xlsx",
        )
    if st.button("Clear conversation", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# Main area — welcome / landing when navigating to the root page
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("# Lumina")
st.markdown(
    "<p class='page-subtitle'>"
    "Upload data and explore it through AI-powered chat, dashboards, graphs, and predictions.</p>",
    unsafe_allow_html=True,
)
st.markdown("---")

if st.session_state.df is None:
    st.markdown(
        """
        <div class="welcome-hero">
            <h2>Upload data to analyze</h2>
            <p>Upload Excel or CSV from the sidebar, or load the built-in sample workbook.</p>
            <div class="pill-hint">Sandboxed Python · Gemini · Plotly · Pandas</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Load sample data", type="primary", use_container_width=True):
            with st.spinner("Loading..."):
                _load_demo_into_session()
            st.rerun()
    with c2:
        st.caption("Or use **Upload** in the sidebar →")
else:
    # Show a navigation guide when data is loaded
    df = st.session_state.df
    fn = st.session_state.file_name or "your file"
    st.success(f"**{fn}** loaded — {len(df):,} rows × {df.shape[1]} columns")
    st.markdown("")
    st.markdown("Navigate using the sidebar pages:")

    cards = st.columns(4)
    with cards[0]:
        st.markdown("### Chat")
        st.caption("Ask questions in plain English. Get tables, metrics, and interactive charts.")
    with cards[1]:
        st.markdown("### Insights")
        st.caption("Auto-generated data profile: distributions, correlations, outliers, trends.")
    with cards[2]:
        st.markdown("### Graph")
        st.caption("Entity relationship graph — see how columns connect across datasets.")
    with cards[3]:
        st.markdown("### Predictions")
        st.caption("Optional AI-powered trend predictions and causal factor analysis.")
