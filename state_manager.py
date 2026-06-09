"""
state_manager.py
────────────────
Canonical session-state keys for the multi-page Lumina app.

Every page must call `init_state()` as its first action so that keys exist
regardless of which page the user navigates to first.

Design rule: if you need a new key, add it to _DEFAULTS here — never
create keys ad-hoc in individual page files.
"""

from __future__ import annotations

import os
from typing import Any

import streamlit as st


# ── Canonical defaults ────────────────────────────────────────────────────────

_DEFAULTS: dict[str, Any] = {
    # ── Active dataset ─────────────────────────────────────────────────────
    "df":               None,   # pd.DataFrame — current active sheet
    "all_sheets":       {},     # sheet_name → DataFrame (all sheets in workbook)
    "sheet_name":       None,   # str — name of the active sheet
    "schema_desc":      "",     # str — LLM-friendly schema for active sheet
    "sample_rows":      "",     # str — first 5 rows as markdown table
    "file_name":        None,   # str — original uploaded file name
    "file_fingerprint": None,   # str — content signature to detect same-name re-uploads

    # ── Chat ───────────────────────────────────────────────────────────────
    "chat_history":     [],     # [{"role": "user"|"assistant", "content": str, "extra": dict}]
    "_prefill":         None,   # str | None — pre-fill text for chat input

    # ── Computed on upload (not per-turn) ──────────────────────────────────
    "profile":          None,   # DataProfile from insight_engine (auto-generated)
    "graph_meta":       None,   # GraphMeta from graph_engine (current file)

    # ── Predictions / Causes (cached per file, user-triggered) ────────────
    "predictions_text": None,   # str | None
    "causes_text":      None,   # str | None
    "predictions_file": None,   # str — file_name when predictions were generated
    "predictions_sheet": None,  # str — sheet_name when predictions were generated

    # ── API key (resolved once in sidebar) ────────────────────────────────
    "api_key":          "",
}


# ── Public API ────────────────────────────────────────────────────────────────

def init_state() -> None:
    """Idempotent — safe to call at the top of every page."""
    for key, default in _DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = default


def clear_data_state() -> None:
    """
    Reset all data-derived keys when a new file is loaded.
    Preserves api_key so the user doesn't have to re-enter it.
    """
    data_keys = [
        "df", "all_sheets", "sheet_name", "schema_desc", "sample_rows",
        "file_name", "file_fingerprint", "chat_history", "profile",
        "graph_meta", "predictions_text", "causes_text", "predictions_file", "predictions_sheet",
    ]
    for key in data_keys:
        st.session_state[key] = _DEFAULTS[key]


def resolve_api_key() -> str:
    """
    Resolve the Gemini API key in priority order:
      1. GEMINI_API_KEY from .env / environment
      2. Streamlit secrets (for cloud deployments)
      3. st.session_state.api_key (user typed it in sidebar)
    Returns empty string if none available.
    """
    key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if key:
        return key
    try:
        return str(st.secrets["GEMINI_API_KEY"]).strip()
    except Exception:
        pass
    return (st.session_state.get("api_key") or "").strip()
