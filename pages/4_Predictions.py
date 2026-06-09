"""
pages/4_Predictions.py
─────────────────────────
Lumina — LLM-powered Predictions and Causal Analysis.

Both analyses are OPTIONAL — never run automatically to avoid unexpected
API costs. The user clicks "Generate" to trigger the LLM call. Results
are cached in session state per file so navigating away and back doesn't
re-run them.

Tabs:
  1. Predictions  — trend forecasts (3–5 structured insight cards)
  2. Causes       — causal factor analysis (up to 4 structured cards)
"""

from __future__ import annotations

import streamlit as st

from gemini_llm import GeminiLLM
from state_manager import init_state, resolve_api_key
from ui_theme import CSS_BLOCK, section_header

# ── Init ──────────────────────────────────────────────────────────────────────
init_state()
st.markdown(CSS_BLOCK, unsafe_allow_html=True)

st.markdown("# Predictions & Analysis")
st.markdown(
    '<div class="page-subtitle">Optional LLM-powered trend predictions and causal factor identification. Never runs automatically.</div>',
    unsafe_allow_html=True,
)
st.markdown("---")

# ── Guard: require loaded data ────────────────────────────────────────────────
if st.session_state.df is None:
    st.info("Upload a file or load sample data from the sidebar first.")
    st.stop()

api_key = resolve_api_key()
if not api_key:
    st.warning("Enter a Gemini API key in the sidebar to use this feature.")
    st.stop()

schema_desc = st.session_state.schema_desc
profile = st.session_state.profile
file_name = st.session_state.file_name or ""
sheet_name = st.session_state.sheet_name or ""

# ── Build statistical summary for LLM ────────────────────────────────────────
stat_summary = profile.statistical_summary if profile else schema_desc

top_corr_text = ""
if profile and profile.top_corr_pairs:
    top_corr_text = "\n".join(
        f"  {a} ↔ {b}: r = {r:+.3f}" for a, b, r in profile.top_corr_pairs
    )
else:
    top_corr_text = "No correlation data available."

# ── Helper: cached check ──────────────────────────────────────────────────────
def _is_cached(key: str) -> bool:
    """True if the result was generated for the currently loaded file."""
    return (
        st.session_state.get("predictions_file") == file_name
        and st.session_state.get("predictions_sheet") == sheet_name
        and st.session_state.get(key) is not None
    )

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_pred, tab_cause = st.tabs(["Predictions", "Causes Analysis"])

# ────────────────────────── Predictions tab ───────────────────────────────────
with tab_pred:
    st.markdown("### What trends are likely to continue?")
    st.markdown(
        "<p style='color:#8b949e;'>Gemini will analyze your dataset schema and statistics "
        "to forecast 3–5 trends, with evidence and confidence levels.</p>",
        unsafe_allow_html=True,
    )

    if _is_cached("predictions_text"):
        st.markdown(st.session_state.predictions_text)
        st.markdown("---")
        col_a, col_b = st.columns([1, 3])
        with col_a:
            if st.button("Regenerate", key="regen_pred"):
                st.session_state.predictions_text = None
                st.rerun()
        with col_b:
            st.caption("Results are cached for this file. Click regenerate to refresh.")
    else:
        st.markdown("")
        if st.button("Generate Predictions", type="primary", use_container_width=False):
            with st.spinner("Asking Gemini for trend predictions… (this may take 10–20 s)"):
                try:
                    llm = GeminiLLM(api_key=api_key)
                    text = llm.generate_predictions(
                        schema_description=schema_desc,
                        statistical_summary=stat_summary,
                    )
                    st.session_state.predictions_text = text
                    st.session_state.predictions_file = file_name
                    st.session_state.predictions_sheet = sheet_name
                except Exception as exc:
                    st.error(f"Generation failed: {exc}")
            st.rerun()
        else:
            st.markdown(
                '<div class="empty-state">'
                '<p>Click <strong>Generate Predictions</strong> to see AI-powered trend forecasts.</p>'
                '<p style="font-size:0.8rem;color:#4a5568;">Uses your dataset schema and statistical profile as context.</p>'
                '</div>',
                unsafe_allow_html=True,
            )

# ────────────────────────── Causes tab ───────────────────────────────────────
with tab_cause:
    st.markdown("### What factors are driving the patterns?")
    st.markdown(
        "<p style='color:#8b949e;'>Gemini will examine correlations and distributions "
        "to identify up to 4 likely causal factors in your data.</p>",
        unsafe_allow_html=True,
    )

    if _is_cached("causes_text"):
        st.markdown(st.session_state.causes_text)
        st.markdown("---")
        col_a, col_b = st.columns([1, 3])
        with col_a:
            if st.button("Regenerate", key="regen_cause"):
                st.session_state.causes_text = None
                st.rerun()
        with col_b:
            st.caption("Results are cached for this file. Click regenerate to refresh.")
    else:
        st.markdown("")
        if st.button("Analyze Causes", type="primary", use_container_width=False):
            with st.spinner("Asking Gemini for causal analysis… (this may take 10–20 s)"):
                try:
                    llm = GeminiLLM(api_key=api_key)
                    text = llm.generate_causes(
                        schema_description=schema_desc,
                        statistical_summary=stat_summary,
                        top_correlations=top_corr_text,
                    )
                    st.session_state.causes_text = text
                    st.session_state.predictions_file = file_name
                    st.session_state.predictions_sheet = sheet_name
                except Exception as exc:
                    st.error(f"Generation failed: {exc}")
            st.rerun()
        else:
            st.markdown(
                '<div class="empty-state">'
                '<p>Click <strong>Analyze Causes</strong> to identify likely driving factors.</p>'
                '<p style="font-size:0.8rem;color:#4a5568;">Uses top correlations and statistical summary as evidence.</p>'
                '</div>',
                unsafe_allow_html=True,
            )

# ── Footer note ───────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    '<div class="disclaimer">'
    'These predictions and causal analyses are generated by an LLM and are based solely on '
    'the dataset schema and statistics — not the raw data rows. '
    'They are suggestions for exploration, not definitive conclusions. '
    'Always validate findings with domain expertise.'
    '</div>',
    unsafe_allow_html=True,
)
