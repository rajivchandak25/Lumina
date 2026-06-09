"""
pages/3_Graph.py
─────────────────────
Lumina — Entity Relationship Graph Visualizer.

Shows:
  • Current file: entity/numeric/datetime/text columns as nodes,
    with correlation, co-occurrence, and shared-name edges
  • All sessions (cross-dataset): shows how column names and relationships
    connect across every file ever uploaded in this installation

The graph is stored in SQLite (excелchat.db) and persists across sessions.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from graph_engine import build_plotly_graph, get_all_files, load_full_graph
from state_manager import init_state
from ui_theme import CSS_BLOCK, section_header, kpi_card

# ── Init ──────────────────────────────────────────────────────────────────────
init_state()
st.markdown(CSS_BLOCK, unsafe_allow_html=True)

st.markdown("# Entity Relationship Graph")
st.markdown('<div class="page-subtitle">Column relationships within and across datasets — powered by correlation, co-occurrence, and cross-session shared names.</div>', unsafe_allow_html=True)
st.markdown("---")

# ── View mode toggle ──────────────────────────────────────────────────────────
view_mode = st.radio(
    "View",
    ["Current file", "All sessions (cross-dataset)"],
    horizontal=True,
    help="'All sessions' shows relationships detected across every file uploaded to this app.",
)

# ── Select graph data ─────────────────────────────────────────────────────────
if view_mode == "Current file":
    meta = st.session_state.graph_meta
    if meta is None:
        st.info("Upload a file or load sample data from the sidebar to build the graph.")
        st.stop()
else:
    with st.spinner("Loading cross-session graph…"):
        meta = load_full_graph()
    if not meta.nodes:
        st.info("No data in the graph yet. Upload files to populate the cross-session view.")
        st.stop()

# ── Graph title / stats ───────────────────────────────────────────────────────
rel_types = set(e["rel"] for e in meta.edges)

kpi_html = (
    '<div class="kpi-strip" style="grid-template-columns:repeat(3,1fr);">'
    + kpi_card(str(len(meta.nodes)), "Columns")
    + kpi_card(str(len(meta.edges)), "Relationships")
    + kpi_card(str(len(rel_types)), "Relationship types")
    + '</div>'
)
st.markdown(kpi_html, unsafe_allow_html=True)

# ── Legend ────────────────────────────────────────────────────────────────────
st.markdown(
    "<div class='graph-legend'>"
    "<span style='color:#58d9c8;'>● Entity column</span>"
    "<span style='color:#79c0ff;'>● Numeric column</span>"
    "<span style='color:#ffa657;'>● DateTime / ID column</span>"
    "<span style='color:#8b949e;'>● Text column</span>"
    "<span style='color:#8b949e;'>── Correlation (numeric↔numeric)</span>"
    "<span style='color:#8b949e;'>── Co-occurrence (categorical↔categorical)</span>"
    "<span style='color:#ffa657;'>── Shared name (cross-dataset join key)</span>"
    "</div>",
    unsafe_allow_html=True,
)

# ── Main graph ────────────────────────────────────────────────────────────────
with st.spinner("Rendering graph…"):
    fig = build_plotly_graph(meta)

st.markdown('<div class="graph-card">', unsafe_allow_html=True)
st.plotly_chart(
    fig,
    use_container_width=True,
    config={
        "scrollZoom":      True,
        "displayModeBar":  True,
        "modeBarButtonsToRemove": ["lasso2d", "select2d"],
    },
)
st.markdown('</div>', unsafe_allow_html=True)

st.caption("Scroll to zoom · Drag to pan · Hover nodes for details · Double-click to reset view")

st.markdown("---")

# ── Relationship table ────────────────────────────────────────────────────────
if meta.edges:
    st.markdown(section_header("Detected Relationships"), unsafe_allow_html=True)

    edge_rows = []
    for e in meta.edges:
        src_label = e["source"].split("::")[-1]
        tgt_label = e["target"].split("::")[-1]
        src_file  = "::".join(e["source"].split("::")[:-1])
        tgt_file  = "::".join(e["target"].split("::")[:-1])
        edge_rows.append({
            "Column A":       src_label,
            "Column B":       tgt_label,
            "Relationship":   e["rel"].replace("_", " ").title(),
            "Strength":       round(e["weight"], 3),
            "File A":         src_file,
            "File B":         tgt_file,
        })

    edge_df = pd.DataFrame(edge_rows).sort_values("Strength", ascending=False)
    st.dataframe(edge_df, use_container_width=True, hide_index=True)

    # Cross-dataset join key candidates
    shared = [e for e in meta.edges if e["rel"] == "shared_name"]
    if shared:
        st.markdown("---")
        st.markdown(section_header("Potential Join Keys (Cross-Dataset)"), unsafe_allow_html=True)
        st.caption(
            "These column names appear in multiple uploaded files — "
            "they may represent the same entity and could be used to join the datasets."
        )
        for e in shared:
            src_col  = e["source"].split("::")[-1]
            src_file = e["source"].split("::")[0]
            tgt_file = e["target"].split("::")[0]
            st.markdown(
                f'<div class="join-card">'
                f'<span style="color:#ffa657;font-family:\'DM Mono\',monospace;">{src_col}</span> — '
                f'appears in <strong>{src_file}</strong> and <strong>{tgt_file}</strong><br>'
                f'<span class="badge" style="background:#1a2233;color:#8d9db0;border:1px solid #1e2d40;font-size:0.7rem;">Potential join key</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

st.markdown("---")

# ── Registered files history ──────────────────────────────────────────────────
if view_mode == "All sessions (cross-dataset)":
    st.markdown(section_header("Registered Files"), unsafe_allow_html=True)
    st.caption("Files whose schemas have been stored in the local SQLite graph database.")
    files = get_all_files()
    if files:
        files_df = pd.DataFrame(files).rename(columns={
            "file": "File", "sheet": "Sheet", "at": "Registered at",
            "rows": "Rows", "cols": "Columns",
        })
        st.dataframe(files_df, use_container_width=True, hide_index=True)
    else:
        st.info("No files registered yet.")
