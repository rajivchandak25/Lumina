"""
ui_theme.py
───────────
Single source of truth for Lumina's visual design system.

Every page imports CSS_BLOCK and applies it via:
    st.markdown(CSS_BLOCK, unsafe_allow_html=True)

Every Plotly chart merges PLOTLY_LAYOUT:
    fig.update_layout(**PLOTLY_LAYOUT)
"""

from __future__ import annotations

# ── Color tokens ──────────────────────────────────────────────────────────────
BG_BASE     = "#0a0e17"
BG_SURFACE  = "#111827"
BG_RAISED   = "#1a2233"
BORDER      = "#1e2d40"
BORDER_LIT  = "#2a3f5a"
ACCENT      = "#2dd4bf"
ACCENT_DIM  = "#0d9488"
TEXT_PRI    = "#f0f6fc"
TEXT_SEC    = "#8d9db0"
TEXT_DIM    = "#4a5568"
AMBER       = "#ffa657"
RED_DIM     = "#f85149"

# ── Shared Plotly layout dict ─────────────────────────────────────────────────
PLOTLY_LAYOUT: dict = dict(
    template="plotly_dark",
    paper_bgcolor=BG_BASE,
    plot_bgcolor=BG_SURFACE,
    font=dict(family="DM Sans, sans-serif", color=TEXT_SEC, size=12),
    title_font=dict(family="DM Sans, sans-serif", color=TEXT_PRI, size=14),
    margin=dict(l=16, r=16, t=44, b=16),
    hoverlabel=dict(
        bgcolor=BG_RAISED,
        bordercolor=BORDER_LIT,
        font_size=12,
        font_family="DM Sans, sans-serif",
    ),
    xaxis=dict(
        gridcolor=BORDER,
        zerolinecolor=BORDER,
        tickfont=dict(color=TEXT_DIM, size=11),
    ),
    yaxis=dict(
        gridcolor=BORDER,
        zerolinecolor=BORDER,
        tickfont=dict(color=TEXT_DIM, size=11),
    ),
)


# ── CSS block ─────────────────────────────────────────────────────────────────
CSS_BLOCK = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&family=Playfair+Display:wght@700&display=swap');

/* ── Keyframe animations ── */
@keyframes fadeInUp {{
  from {{ opacity: 0; transform: translateY(8px); }}
  to   {{ opacity: 1; transform: translateY(0);   }}
}}
@keyframes slideInUp {{
  from {{ opacity: 0; transform: translateY(12px); }}
  to   {{ opacity: 1; transform: translateY(0);    }}
}}
@keyframes pulseBorder {{
  0%, 100% {{ box-shadow: 0 0 0 0   rgba(45,212,191,0.35); }}
  50%       {{ box-shadow: 0 0 0 5px rgba(45,212,191,0);    }}
}}
@keyframes dotPulse {{
  0%, 80%, 100% {{ transform: scale(0.6); opacity: 0.4; }}
  40%           {{ transform: scale(1.0); opacity: 1.0; }}
}}

/* ── Base ── */
html, body, [data-testid="stAppViewContainer"] {{
  background: {BG_BASE};
  color: {TEXT_PRI};
  font-family: 'DM Sans', sans-serif;
}}
[data-testid="stHeader"] {{ background: transparent; box-shadow: none; }}

/* ── Sidebar ── */
[data-testid="stSidebar"] {{
  background: {BG_SURFACE};
  border-right: 1px solid {BORDER};
}}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {{
  font-family: 'DM Sans', sans-serif;
  font-weight: 500;
  font-size: 0.92rem;
  color: {TEXT_SEC};
}}

/* Sidebar nav links */
[data-testid="stSidebarNav"] {{
  padding-top: 0.5rem;
}}
[data-testid="stSidebarNav"] a {{
  color: {TEXT_SEC} !important;
  font-family: 'DM Sans', sans-serif;
  font-size: 0.875rem;
  font-weight: 400;
  border-radius: 6px;
  padding: 0.35rem 0.75rem;
  border-left: 3px solid transparent;
  transition: all 0.15s ease;
}}
[data-testid="stSidebarNav"] a:hover {{
  color: {TEXT_PRI} !important;
  background: {BG_RAISED} !important;
  border-left-color: {ACCENT};
}}
[data-testid="stSidebarNav"] a[aria-current="page"] {{
  color: {ACCENT} !important;
  background: rgba(45,212,191,0.08) !important;
  border-left-color: {ACCENT};
  font-weight: 500;
}}

/* ── Buttons ── */
.stButton > button {{
  background: transparent;
  color: {TEXT_SEC};
  font-weight: 500;
  border: 1px solid {BORDER};
  border-radius: 7px;
  padding: 0.42rem 1rem;
  font-family: 'DM Sans', sans-serif;
  font-size: 0.875rem;
  transition: all 0.15s ease;
  border-left: 3px solid transparent;
}}
.stButton > button:hover {{
  color: {TEXT_PRI};
  background: {BG_RAISED};
  border-color: {BORDER_LIT};
  border-left-color: {ACCENT};
  transform: none;
}}
.stButton > button:focus {{
  box-shadow: 0 0 0 2px rgba(45,212,191,0.2);
  outline: none;
}}
.stButton > button[kind="primary"] {{
  background: transparent;
  border-color: {ACCENT_DIM};
  color: {ACCENT};
  border-left-color: {ACCENT};
  animation: pulseBorder 2.5s ease-in-out infinite;
}}
.stButton > button[kind="primary"]:hover {{
  background: rgba(13,148,136,0.15);
  border-color: {ACCENT};
  color: {TEXT_PRI};
  animation: none;
}}
.stButton > button:disabled {{
  background: transparent;
  color: {TEXT_DIM};
  border-color: {BORDER};
  border-left-color: transparent;
  animation: none;
}}

/* ── File uploader ── */
[data-testid="stFileUploader"] {{
  background: {BG_RAISED};
  border: 1.5px dashed {BORDER_LIT};
  border-radius: 8px;
  padding: 0.5rem;
  transition: border-color 0.2s ease;
}}
[data-testid="stFileUploader"]:hover {{
  border-color: {ACCENT};
}}

/* ── Inputs ── */
[data-testid="stChatInput"] textarea,
.stTextInput input,
.stSelectbox select {{
  background: {BG_RAISED} !important;
  border: 1.5px solid {BORDER} !important;
  border-radius: 8px !important;
  color: {TEXT_PRI} !important;
  font-family: 'DM Sans', sans-serif !important;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}}
[data-testid="stChatInput"] textarea:focus,
.stTextInput input:focus {{
  border-color: {ACCENT} !important;
  box-shadow: 0 0 0 3px rgba(45,212,191,0.12) !important;
}}

/* ── Chat messages ── */
[data-testid="stChatMessage"] {{
  background: {BG_SURFACE};
  border: none;
  border-radius: 10px;
  padding: 0.75rem 1rem;
  margin-bottom: 0.75rem;
  box-shadow: 0 1px 3px rgba(0,0,0,0.4);
  animation: slideInUp 0.2s ease both;
}}
[data-testid="stChatMessage"] p {{
  color: {TEXT_PRI};
  font-size: 0.92rem;
  line-height: 1.6;
}}

/* ── Expanders ── */
[data-testid="stExpander"] {{
  background: {BG_RAISED};
  border: 1px solid {BORDER};
  border-radius: 8px;
  overflow: hidden;
}}
[data-testid="stExpander"] summary {{
  color: {TEXT_SEC};
  font-size: 0.85rem;
  font-weight: 500;
  padding: 0.6rem 0.8rem;
}}
[data-testid="stExpander"] summary:hover {{
  color: {TEXT_PRI};
}}

/* ── Metrics ── */
[data-testid="metric-container"] {{
  background: {BG_RAISED};
  border: 1px solid {BORDER};
  border-radius: 8px;
  padding: 0.75rem 1rem;
}}
[data-testid="metric-container"] [data-testid="stMetricValue"] {{
  font-family: 'DM Mono', monospace;
  color: {TEXT_PRI};
  font-size: 1.4rem;
}}
[data-testid="metric-container"] [data-testid="stMetricLabel"] {{
  color: {TEXT_DIM};
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}}

/* ── DataFrames ── */
[data-testid="stDataFrame"] {{
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid {BORDER};
}}

/* ── Dividers ── */
hr {{
  border: none;
  border-top: 1px solid {BORDER};
  margin: 1rem 0;
}}

/* ── Headings ── */
h1 {{
  font-family: 'Playfair Display', serif !important;
  font-size: 1.8rem;
  color: {TEXT_PRI};
  margin-bottom: 0 !important;
}}
h2, h3 {{
  font-family: 'DM Sans', sans-serif !important;
  font-weight: 600;
  color: {TEXT_PRI};
}}

/* ── Section header rule ── */
.section-header {{
  border-bottom: 1px solid {BORDER};
  padding-bottom: 0.6rem;
  margin-bottom: 1rem;
  font-family: 'DM Sans', sans-serif;
  font-weight: 600;
  font-size: 1rem;
  color: {TEXT_PRI};
}}

/* ── Schema box ── */
.schema-box {{
  background: {BG_RAISED};
  border: 1px solid {BORDER};
  border-radius: 8px;
  padding: 0.8rem 1rem;
  font-family: 'DM Mono', monospace;
  font-size: 0.78rem;
  color: {TEXT_SEC};
  white-space: pre-wrap;
  overflow-x: auto;
  max-height: 260px;
  overflow-y: auto;
}}

/* ── KPI strip ── */
.kpi-strip {{
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 0.75rem;
  margin-bottom: 1rem;
}}

/* ── KPI card ── */
.kpi-card {{
  background: {BG_SURFACE};
  border: 1px solid {BORDER};
  border-radius: 10px;
  padding: 1rem 1.25rem;
  box-shadow: 0 1px 3px rgba(0,0,0,0.4);
  animation: fadeInUp 0.4s ease both;
  transition: all 0.2s ease;
}}
.kpi-card:hover {{
  box-shadow: 0 4px 12px rgba(0,0,0,0.5), 0 1px 3px rgba(0,0,0,0.3);
  border-color: {BORDER_LIT};
}}
.kpi-card.warning {{ border-left: 3px solid {ACCENT}; }}
.kpi-value {{
  font-family: 'DM Mono', monospace;
  font-size: 1.6rem;
  font-weight: 400;
  color: {TEXT_PRI};
  line-height: 1.2;
}}
.kpi-label {{
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: {TEXT_DIM};
  margin-top: 0.25rem;
}}

/* ── Chart card ── */
.chart-card {{
  background: {BG_SURFACE};
  border: 1px solid {BORDER};
  border-radius: 10px;
  padding: 0;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0,0,0,0.4);
  transition: box-shadow 0.2s ease, border-color 0.2s ease;
  animation: fadeInUp 0.4s ease both;
}}
.chart-card:hover {{
  box-shadow: 0 0 20px rgba(45,212,191,0.12), 0 4px 12px rgba(0,0,0,0.5);
  border-color: {BORDER_LIT};
}}

/* ── Graph card ── */
.graph-card {{
  background: {BG_SURFACE};
  border: 1px solid {BORDER};
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0,0,0,0.5), 0 1px 3px rgba(0,0,0,0.3);
  transition: box-shadow 0.25s ease;
  animation: fadeInUp 0.3s ease both;
}}
.graph-card:hover {{
  box-shadow: 0 0 30px rgba(45,212,191,0.08), 0 4px 16px rgba(0,0,0,0.6);
}}

/* ── Graph legend ── */
.graph-legend {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 1.5rem;
  padding: 0.75rem 1rem;
  background: {BG_RAISED};
  border: 1px solid {BORDER};
  border-radius: 8px;
  margin-bottom: 0.75rem;
  font-size: 0.85rem;
}}

/* ── Insight cards (Predictions page) ── */
.insight-card {{
  background: {BG_SURFACE};
  border: 1px solid {BORDER};
  border-radius: 10px;
  padding: 1.1rem 1.25rem;
  margin-bottom: 0.75rem;
  box-shadow: 0 1px 3px rgba(0,0,0,0.4);
}}
.insight-card.prediction {{ border-left: 3px solid {ACCENT}; }}
.insight-card.cause       {{ border-left: 3px solid {AMBER}; }}
.insight-card-title {{
  font-family: 'DM Sans', sans-serif;
  font-weight: 600;
  font-size: 0.95rem;
  color: {TEXT_PRI};
  margin-bottom: 0.6rem;
}}
.insight-field-label {{
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: {TEXT_DIM};
  margin-top: 0.5rem;
  margin-bottom: 0.15rem;
}}
.insight-field-value {{
  font-size: 0.88rem;
  color: {TEXT_SEC};
  line-height: 1.55;
}}
.badge {{
  display: inline-block;
  padding: 0.15rem 0.55rem;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 500;
  letter-spacing: 0.03em;
}}
.badge-high   {{ background: rgba(45,212,191,0.15);  color: {ACCENT}; }}
.badge-medium {{ background: rgba(255,166,87,0.15);  color: {AMBER};  }}
.badge-low    {{ background: rgba(74,85,104,0.25);   color: {TEXT_SEC}; }}

/* ── Join key card ── */
.join-card {{
  background: {BG_SURFACE};
  border: 1px solid {BORDER};
  border-left: 3px solid {ACCENT};
  border-radius: 8px;
  padding: 0.7rem 1rem;
  margin-bottom: 0.5rem;
}}
.join-card-col {{
  font-family: 'DM Mono', monospace;
  font-size: 0.88rem;
  color: {ACCENT};
  font-weight: 500;
}}
.join-card-files {{
  font-size: 0.82rem;
  color: {TEXT_SEC};
  margin-top: 0.2rem;
}}

/* ── Correlation chip ── */
.corr-chip {{
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  background: {BG_RAISED};
  border: 1px solid {BORDER};
  border-radius: 6px;
  padding: 0.35rem 0.7rem;
  margin: 0.25rem 0.25rem 0.25rem 0;
  font-size: 0.82rem;
  color: {TEXT_SEC};
}}
.corr-r-pos {{ color: {ACCENT}; font-family: 'DM Mono', monospace; font-size: 0.8rem; }}
.corr-r-neg {{ color: {AMBER};  font-family: 'DM Mono', monospace; font-size: 0.8rem; }}

/* ── Empty state ── */
.empty-state {{
  border: 1px dashed {BORDER_LIT};
  border-radius: 12px;
  padding: 3rem 2rem;
  text-align: center;
  color: {TEXT_SEC};
}}
.empty-state-icon {{
  font-size: 1.5rem;
  color: {ACCENT};
  margin-bottom: 0.75rem;
  font-family: monospace;
}}
.empty-state-title {{
  font-family: 'DM Sans', sans-serif;
  font-weight: 500;
  font-size: 1rem;
  color: {TEXT_PRI};
  margin-bottom: 0.4rem;
}}
.empty-state-sub {{
  font-size: 0.85rem;
  color: {TEXT_SEC};
  max-width: 320px;
  margin: 0 auto;
}}

/* ── Pill tab buttons ── */
.pill-tabs {{
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
}}
.pill-tab {{
  padding: 0.4rem 1rem;
  border-radius: 999px;
  font-size: 0.875rem;
  font-family: 'DM Sans', sans-serif;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid {BORDER};
  background: {BG_RAISED};
  color: {TEXT_SEC};
  transition: all 0.15s ease;
}}
.pill-tab.active {{
  background: {ACCENT_DIM};
  color: {TEXT_PRI};
  border-color: {ACCENT_DIM};
}}

/* ── Follow-up buttons ── */
.followup-btn button {{
  border-radius: 999px !important;
  font-size: 0.8rem !important;
  padding: 0.3rem 0.8rem !important;
  border-left-width: 1px !important;
  color: {TEXT_SEC} !important;
  animation: fadeInUp 0.3s ease both;
}}

/* ── Disclaimer ── */
.disclaimer {{
  border-top: 1px solid {BORDER};
  padding-top: 0.75rem;
  margin-top: 1rem;
  font-size: 0.75rem;
  color: {TEXT_DIM};
  line-height: 1.5;
}}

/* ── Relationship badge ── */
.rel-badge {{
  display: inline-block;
  padding: 0.12rem 0.5rem;
  border-radius: 4px;
  font-size: 0.72rem;
  font-weight: 500;
}}
.rel-badge-corr   {{ background: rgba(121,192,255,0.15); color: #79c0ff; }}
.rel-badge-cooc   {{ background: rgba(45,212,191,0.15);  color: {ACCENT}; }}
.rel-badge-shared {{ background: rgba(255,166,87,0.15);  color: {AMBER}; }}

/* ── Streamlit native overrides ── */
[data-testid="stVerticalBlockBorderWrapper"] > div {{ gap: 0.5rem; }}
.stTabs [data-baseweb="tab-list"] {{ background: {BG_RAISED}; border-radius: 8px; padding: 4px; gap: 8px; }}
.stTabs [data-baseweb="tab"] {{ border-radius: 6px; color: {TEXT_SEC}; font-size: 0.875rem; padding: 0.4rem 1.2rem; }}
.stTabs [aria-selected="true"] {{ background: {BG_SURFACE}; color: {TEXT_PRI}; }}

/* ── Page subtitle ── */
.page-subtitle {{
  color: {TEXT_SEC};
  font-size: 0.95rem;
  margin-top: -0.4rem;
  margin-bottom: 0;
}}

/* ── Sidebar wordmark ── */
.sidebar-wordmark {{
  font-family: 'DM Sans', sans-serif;
  font-weight: 500;
  font-size: 1rem;
  color: {TEXT_SEC};
  letter-spacing: 0.01em;
  margin-bottom: 1.2rem;
}}

/* ── Sidebar section label ── */
.sidebar-section-label {{
  font-family: 'DM Sans', sans-serif;
  font-size: 0.65rem;
  font-weight: 500;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: {TEXT_DIM};
  margin-bottom: 0.5rem;
  margin-top: 0.75rem;
}}

/* ── Welcome hero ── */
.welcome-hero {{
  text-align: center;
  padding: 4rem 1rem;
}}
.welcome-hero h2 {{
  font-family: 'Playfair Display', serif !important;
  font-size: 1.75rem;
  color: {ACCENT};
  margin: 0.5rem 0;
}}
.welcome-hero p {{ color: {TEXT_SEC}; font-size: 0.95rem; }}
.pill-hint {{
  display: inline-block;
  margin-top: 1rem;
  padding: 0.3rem 0.75rem;
  border-radius: 999px;
  background: {BG_RAISED};
  border: 1px solid {BORDER};
  font-size: 0.78rem;
  color: {TEXT_DIM};
  font-family: 'DM Mono', monospace;
}}
</style>
"""


def kpi_card(value: str, label: str, warning: bool = False) -> str:
    """Return HTML for a single KPI metric card."""
    cls = "kpi-card warning" if warning else "kpi-card"
    return (
        f'<div class="{cls}">'
        f'<div class="kpi-value">{value}</div>'
        f'<div class="kpi-label">{label}</div>'
        f'</div>'
    )


def section_header(title: str) -> str:
    """Return HTML for a section header with bottom border rule."""
    return f'<div class="section-header">{title}</div>'


def insight_card_html(title: str, confidence: str, evidence: str, forecast: str) -> str:
    """Return HTML for a prediction insight card."""
    badge_cls = f"badge badge-{confidence.lower()}" if confidence.lower() in ("high", "medium", "low") else "badge badge-low"
    return (
        f'<div class="insight-card prediction">'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:0.5rem;">'
        f'<div class="insight-card-title">{title}</div>'
        f'<span class="{badge_cls}">{confidence}</span>'
        f'</div>'
        f'<div class="insight-field-label">Evidence</div>'
        f'<div class="insight-field-value">{evidence}</div>'
        f'<div class="insight-field-label">Forecast</div>'
        f'<div class="insight-field-value">{forecast}</div>'
        f'</div>'
    )


def cause_card_html(title: str, metric: str, driver: str, signal: str) -> str:
    """Return HTML for a causes analysis card."""
    return (
        f'<div class="insight-card cause">'
        f'<div class="insight-card-title">{title}</div>'
        f'<div class="insight-field-label">Affected Metric</div>'
        f'<div class="insight-field-value">{metric}</div>'
        f'<div class="insight-field-label">Likely Driver</div>'
        f'<div class="insight-field-value">{driver}</div>'
        f'<div class="insight-field-label">Supporting Signal</div>'
        f'<div class="insight-field-value">{signal}</div>'
        f'</div>'
    )
