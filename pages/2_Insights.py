"""
pages/2_Insights.py
──────────────────────
Lumina — Auto-generated data profile dashboard.

All computation is pre-done in insight_engine.profile_dataframe() at upload
time. This page is purely rendering: it reads st.session_state.profile and
displays interactive Plotly charts.

Sections:
  1. KPI metrics strip
  2. Missing values bar chart
  3. Numeric distributions (histograms)
  4. Correlation matrix heatmap + top pairs
  5. Outlier summary
  6. Category distributions (value counts)
  7. Time series trends (conditional on date columns)
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from state_manager import init_state
from ui_theme import CSS_BLOCK, PLOTLY_LAYOUT, kpi_card, section_header

# ── Init ──────────────────────────────────────────────────────────────────────
init_state()
st.markdown(CSS_BLOCK, unsafe_allow_html=True)

st.markdown("# Data Insights")
st.markdown(
    '<div class="page-subtitle">Auto-generated profile of your dataset — no questions needed.</div>',
    unsafe_allow_html=True,
)
st.markdown("---")

profile = st.session_state.profile
df = st.session_state.df

if profile is None or df is None:
    st.info("Upload a file or load sample data from the sidebar to generate insights.")
    st.stop()

fn = st.session_state.file_name or "your file"
sheet = st.session_state.sheet_name or ""
st.caption(f"File: **{fn}**  ·  Sheet: **{sheet}**")

# ── 1. KPI Metrics ────────────────────────────────────────────────────────────
total_missing = int(profile.missing_counts.sum())
kpi_html = (
    '<div class="kpi-strip">'
    + kpi_card(f"{profile.n_rows:,}", "Rows")
    + kpi_card(str(profile.n_cols), "Columns")
    + kpi_card(str(len(profile.numeric_cols)), "Numeric cols")
    + kpi_card(str(len(profile.categorical_cols)), "Categorical cols")
    + kpi_card(f"{total_missing:,}", "Missing cells", warning=(total_missing > 0))
    + '</div>'
)
st.markdown(kpi_html, unsafe_allow_html=True)

st.markdown("---")

# ── 2. Missing Values ─────────────────────────────────────────────────────────
missing_nonzero = profile.missing_counts[profile.missing_counts > 0]
st.markdown(section_header("Missing Values"), unsafe_allow_html=True)
if missing_nonzero.empty:
    st.success("No missing values found in any column.")
else:
    fig = px.bar(
        x=missing_nonzero.index,
        y=missing_nonzero.values,
        labels={"x": "Column", "y": "Missing count"},
        title=f"Missing Values per Column ({len(missing_nonzero)} columns affected)",
        color=missing_nonzero.values,
        color_continuous_scale=[[0, "#2dd4bf"], [1, "#ffa657"]],
    )
    fig.update_layout(**PLOTLY_LAYOUT, coloraxis_showscale=False)
    fig.update_traces(hovertemplate="%{x}<br>Missing: %{y}<extra></extra>")
    st.plotly_chart(fig, use_container_width=True)

    pct_df = profile.missing_pct[profile.missing_pct > 0].sort_values(ascending=False)
    st.caption("Missing percentages: " + ", ".join(f"**{c}** {v:.1f}%" for c, v in pct_df.items()))

st.markdown("---")

# ── 3. Numeric Distributions ──────────────────────────────────────────────────
if profile.numeric_cols:
    st.markdown(section_header("Numeric Distributions"), unsafe_allow_html=True)

    # Descriptive stats table
    with st.expander("Descriptive Statistics", expanded=False):
        st.dataframe(profile.describe_df.T.style.format("{:.3g}"), use_container_width=True)

    # Histogram grid — 3 per row
    n_num = len(profile.numeric_cols)
    cols_per_row = min(3, n_num)
    for row_start in range(0, n_num, cols_per_row):
        row_cols = profile.numeric_cols[row_start:row_start + cols_per_row]
        grid = st.columns(len(row_cols))
        for col_widget, col_name in zip(grid, row_cols):
            with col_widget:
                series = df[col_name].dropna()
                fig = px.histogram(
                    series,
                    title=col_name,
                    nbins=30,
                    labels={"value": col_name, "count": "Frequency"},
                    color_discrete_sequence=["#2dd4bf"],
                )
                fig.update_layout(
                    **{**PLOTLY_LAYOUT, "margin": dict(l=10, r=10, t=35, b=10)},
                    showlegend=False,
                    height=220,
                )
                fig.update_traces(hovertemplate="%{x:.3g}<br>Count: %{y}<extra></extra>")
                st.markdown('<div class="chart-card">', unsafe_allow_html=True)
                st.plotly_chart(fig, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")

# ── 4. Correlation Analysis ───────────────────────────────────────────────────
if profile.corr_matrix is not None:
    st.markdown(section_header("Correlation Analysis"), unsafe_allow_html=True)

    fig = px.imshow(
        profile.corr_matrix,
        color_continuous_scale="RdBu_r",
        zmin=-1, zmax=1,
        title="Pearson Correlation Matrix",
        text_auto=".2f",
    )
    fig.update_layout(**PLOTLY_LAYOUT)
    fig.update_traces(hovertemplate="%{x} ↔ %{y}<br>r = %{z:.3f}<extra></extra>")
    st.plotly_chart(fig, use_container_width=True)

    if profile.top_corr_pairs:
        chips_html = '<div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;">'
        for col_a, col_b, r in profile.top_corr_pairs:
            sign = "+" if r > 0 else ""
            direction = "positive" if r > 0 else "negative"
            strength = "strong" if abs(r) > 0.7 else "moderate" if abs(r) > 0.4 else "weak"
            badge_color = "#0d9488" if r > 0 else "#d97706"
            chips_html += (
                f'<div class="corr-chip">'
                f'<span style="color:#f0f6fc;font-size:0.82rem;">{col_a} ↔ {col_b}</span>'
                f'<span style="background:{badge_color};color:#fff;border-radius:4px;'
                f'padding:1px 6px;font-size:0.72rem;margin-left:6px;">{sign}{r:.2f}</span>'
                f'<span style="color:#4a5568;font-size:0.72rem;margin-left:4px;">{strength} {direction}</span>'
                f'</div>'
            )
        chips_html += '</div>'
        st.markdown(chips_html, unsafe_allow_html=True)
    else:
        st.caption("No significant correlations detected.")

    st.markdown("---")

# ── 5. Outlier Detection ──────────────────────────────────────────────────────
st.markdown(section_header("Outlier Detection (IQR Method)"), unsafe_allow_html=True)
if not profile.outlier_counts:
    st.success("No outliers detected in any numeric column (IQR method).")
else:
    oc_series = pd.Series(profile.outlier_counts)
    fig = px.bar(
        x=oc_series.index,
        y=oc_series.values,
        labels={"x": "Column", "y": "Outlier count"},
        title="Outliers per Numeric Column",
        color=oc_series.values,
        color_continuous_scale=[[0, "#2dd4bf"], [1, "#ffa657"]],
    )
    fig.update_layout(**PLOTLY_LAYOUT, coloraxis_showscale=False)
    fig.update_traces(hovertemplate="%{x}<br>Outliers: %{y}<extra></extra>")
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Outliers defined as values beyond Q1 − 1.5 × IQR or Q3 + 1.5 × IQR. "
        "Go to Chat to investigate specific rows."
    )

st.markdown("---")

# ── 6. Category Distributions ─────────────────────────────────────────────────
if profile.categorical_cols and profile.value_counts:
    st.markdown(section_header("Category Distributions"), unsafe_allow_html=True)
    tabs = st.tabs([f"  {c}  " for c in profile.categorical_cols if c in profile.value_counts])
    for tab, col_name in zip(tabs, [c for c in profile.categorical_cols if c in profile.value_counts]):
        with tab:
            vc = profile.value_counts[col_name]
            fig = px.bar(
                x=vc.values,
                y=vc.index.astype(str),
                orientation="h",
                title=f"Top {len(vc)} values — {col_name}",
                labels={"x": "Count", "y": col_name},
                color=vc.values,
                color_continuous_scale=[[0, "#111827"], [1, "#2dd4bf"]],
            )
            fig.update_layout(**{**PLOTLY_LAYOUT, "yaxis": dict(autorange="reversed", gridcolor="#1e2d40", zerolinecolor="#1e2d40")}, coloraxis_showscale=False)
            fig.update_traces(hovertemplate="%{y}<br>Count: %{x}<extra></extra>")
            st.plotly_chart(fig, use_container_width=True)
            st.caption(f"{vc.sum():,} non-null values · {len(vc)} unique shown (top {len(vc)})")

    st.markdown("---")

# ── 7. Time Series Trends ─────────────────────────────────────────────────────
if profile.time_series:
    st.markdown(section_header("Time Series Trends"), unsafe_allow_html=True)
    for date_col, ts_series in profile.time_series.items():
        ts_df = ts_series.reset_index()
        ts_df.columns = ["Date", "Value"]
        fig = px.line(
            ts_df,
            x="Date",
            y="Value",
            title=f"Monthly trend — {date_col}",
            markers=True,
            color_discrete_sequence=["#2dd4bf"],
        )
        fig.update_layout(**PLOTLY_LAYOUT)
        fig.update_traces(
            line=dict(width=2),
            marker=dict(size=6),
            hovertemplate="%{x|%b %Y}<br>%{y:,.2f}<extra></extra>",
        )
        # Add trend line (simple moving average)
        if len(ts_df) >= 3:
            ts_df["MA"] = ts_df["Value"].rolling(3, min_periods=1).mean()
            fig.add_scatter(
                x=ts_df["Date"],
                y=ts_df["MA"],
                mode="lines",
                name="3-period MA",
                line=dict(color="#ffa657", dash="dash", width=1.5),
                hovertemplate="MA: %{y:,.2f}<extra></extra>",
            )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

st.caption("Profile computed automatically on file upload. Switch sheets in the sidebar to refresh.")
