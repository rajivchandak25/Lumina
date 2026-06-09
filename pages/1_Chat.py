"""
pages/1_Chat.py
──────────────────
Lumina — Q&A pipeline page.

Features:
  • Natural-language question → Gemini code gen → sandboxed execution → result
  • Self-healing retry (up to 2 attempts on execution failure)
  • Plotly interactive charts + matplotlib fallback
  • Suggested follow-up questions as clickable buttons
  • DataFrame results with CSV + Excel download
"""

from __future__ import annotations

import io
import traceback

import matplotlib
import matplotlib.pyplot as plt
import streamlit as st

from code_executor import CodeExecutor
from export_utils import export_results_to_xlsx
from gemini_llm import GeminiLLM
from state_manager import init_state, resolve_api_key
from ui_theme import CSS_BLOCK

matplotlib.use("Agg")

# ── Init ──────────────────────────────────────────────────────────────────────
init_state()
st.markdown(CSS_BLOCK, unsafe_allow_html=True)

# ── Page header ───────────────────────────────────────────────────────────────
st.markdown("# Chat")
st.markdown(
    '<div class="page-subtitle">Ask questions in plain English — '
    "tables, metrics, and interactive charts from your data.</div>",
    unsafe_allow_html=True,
)
st.markdown("---")

# ── Guard: require loaded data ─────────────────────────────────────────────────
if st.session_state.df is None:
    st.info("No data loaded. Upload a file or load sample data from the sidebar.")
    st.stop()

# ── Cached singletons ─────────────────────────────────────────────────────────

@st.cache_resource
def _get_llm(api_key: str) -> GeminiLLM:
    return GeminiLLM(api_key=api_key)


@st.cache_resource
def _get_executor() -> CodeExecutor:
    return CodeExecutor()


# ── Helpers ───────────────────────────────────────────────────────────────────

_MAX_RETRIES = 2


def _render_extra(extra: dict, turn_idx: int = 0) -> None:
    """Render the optional extra payload attached to an assistant turn."""
    if not extra:
        return

    # Generated code (collapsible)
    if extra.get("code"):
        with st.expander("View generated Python", expanded=False):
            st.code(extra["code"], language="python")

    # Plotly chart (interactive)
    if extra.get("plotly_figure") is not None:
        try:
            st.plotly_chart(extra["plotly_figure"], use_container_width=True, key=f"plotly_{turn_idx}")
        except Exception:
            st.warning("Chart could not be rendered.")

    # Matplotlib chart (static PNG)
    if extra.get("figure_bytes"):
        st.image(extra["figure_bytes"], use_column_width=True)
        st.download_button(
            label="Download chart",
            data=extra["figure_bytes"],
            file_name="chart.png",
            mime="image/png",
            key=f"dl_img_{turn_idx}",
        )

    # DataFrame result
    if "dataframe" in extra and extra["dataframe"] is not None:
        df = extra["dataframe"]
        st.dataframe(df, use_container_width=True)
        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name="result.csv",
                mime="text/csv",
                key=f"dl_csv_{turn_idx}",
            )
        with dl_col2:
            import io as _io
            import pandas as _pd
            buf = _io.BytesIO()
            engine = "xlsxwriter"
            try:
                import xlsxwriter  # noqa: F401
            except Exception:
                engine = "openpyxl"
            with _pd.ExcelWriter(buf, engine=engine) as writer:
                df.to_excel(writer, sheet_name="Result", index=False)
            st.download_button(
                label="Download Excel",
                data=buf.getvalue(),
                file_name="result.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"dl_xl_{turn_idx}",
            )

    # Error traceback (collapsible)
    if extra.get("error_traceback"):
        with st.expander("Technical details", expanded=False):
            st.code(extra["error_traceback"], language="text")

    # Follow-up suggestions
    followups = extra.get("followups") or []
    if followups:
        st.markdown('<div style="margin-top:0.75rem;">', unsafe_allow_html=True)
        st.markdown("Suggested follow-ups:", unsafe_allow_html=True)
        cols = st.columns(min(len(followups), 3))
        for i, q in enumerate(followups[:3]):
            if cols[i].button(q, key=f"fu_{turn_idx}_{i}", use_container_width=True):
                st.session_state["_prefill"] = q
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)


def _record_assistant(text: str, extra: dict) -> None:
    st.session_state.chat_history.append(
        {"role": "assistant", "content": text, "extra": extra}
    )


def _handle_question(question: str) -> None:
    """
    Full Q&A pipeline with self-healing retry:
      1. Record + display user turn
      2. Generate code via Gemini
      3. Execute in sandbox
      4. On failure: retry up to _MAX_RETRIES times with error context
      5. Format result by type (plotly / figure / dataframe / scalar / text)
      6. Generate follow-up question suggestions
      7. Record assistant turn + rerun
    """
    api_key = resolve_api_key()
    if not api_key:
        st.error("No Gemini API key. Enter one in the sidebar.")
        return

    # Record + display user bubble immediately
    st.session_state.chat_history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    try:
        llm = _get_llm(api_key)
    except Exception as e:
        _record_assistant(f"Failed to initialize LLM: {e}", {})
        st.rerun()
        return

    executor = _get_executor()
    extra: dict = {}
    err_tb: str | None = None
    answer = ""

    try:
        # ── Step 1: Generate code ─────────────────────────────────────────
        with st.spinner("Generating analysis code…"):
            llm_response: str = llm.generate_code(
                schema_description=st.session_state.schema_desc,
                sample_rows=st.session_state.sample_rows,
                user_question=question,
                chat_history=st.session_state.chat_history[:-1],
            )
            code: str | None = llm.extract_code(llm_response)

        if not code:
            answer = llm_response.strip() or "I couldn't generate code for that question."
            _record_assistant(answer, extra)
            st.rerun()
            return

        extra["code"] = code

        # ── Step 2: Execute (with self-healing retry) ─────────────────────
        with st.spinner("Running code on your data…"):
            exec_result = executor.run(code, st.session_state.df)

        for attempt in range(_MAX_RETRIES):
            if exec_result.success:
                break
            with st.spinner(f"Code failed — retrying ({attempt + 1}/{_MAX_RETRIES})…"):
                retry_response = llm.generate_retry(
                    original_question=question,
                    failed_code=code,
                    error_message=exec_result.error or "",
                    schema_description=st.session_state.schema_desc,
                    sample_rows=st.session_state.sample_rows,
                )
                new_code = llm.extract_code(retry_response)
                if new_code:
                    code = new_code
                    extra["code"] = code
                exec_result = executor.run(code, st.session_state.df)

        if not exec_result.success:
            answer = (
                "**Execution error** (failed after retries):\n\n"
                f"```\n{exec_result.error}\n```\n\n"
                "Try rephrasing your question."
            )
            _record_assistant(answer, extra)
            st.rerun()
            return

        # ── Step 3: Format result by type ─────────────────────────────────
        rtype = exec_result.result_type
        raw = exec_result.result

        if rtype == "plotly":
            answer = "Here is the interactive chart:"
            extra["plotly_figure"] = raw

        elif rtype == "dataframe":
            n = len(raw)
            answer = f"Here is the result table ({n:,} row{'s' if n != 1 else ''}):"
            extra["dataframe"] = raw

        elif rtype == "figure":
            answer = "Here is the chart:"
            buf = io.BytesIO()
            raw.savefig(
                buf, format="png", dpi=150, bbox_inches="tight",
                facecolor="#0d1117", edgecolor="none",
            )
            plt.close(raw)
            extra["figure_bytes"] = buf.getvalue()

        elif rtype == "scalar":
            answer = f"**Result:** `{raw}`"

        elif rtype == "text":
            answer = str(raw)

        else:
            answer = "Code executed with no visible output."
            if exec_result.stdout:
                answer += f"\n\n```\n{exec_result.stdout.strip()}\n```"

        # ── Step 4: Follow-up suggestions ─────────────────────────────────
        try:
            followups = llm.generate_followups(
                schema_description=st.session_state.schema_desc,
                last_question=question,
                last_answer_summary=answer[:300],
            )
            extra["followups"] = followups
        except Exception:
            extra["followups"] = []

    except Exception:
        err_tb = traceback.format_exc()
        answer = (
            "Something went wrong while processing your request. "
            "Check your connection and API key, then try again."
        )

    if err_tb:
        extra["error_traceback"] = err_tb

    _record_assistant(answer, extra)
    st.rerun()


# ── Render chat history ───────────────────────────────────────────────────────
for i, turn in enumerate(st.session_state.chat_history):
    if turn["role"] == "user":
        with st.chat_message("user"):
            st.markdown(turn["content"])
    else:
        with st.chat_message("assistant"):
            st.markdown(turn["content"])
            _render_extra(turn.get("extra", {}), turn_idx=i)

# ── Chat input ────────────────────────────────────────────────────────────────
prefill = st.session_state.pop("_prefill", None)
user_input: str | None = st.chat_input("e.g. What is the total revenue by region?") or prefill

if user_input:
    _handle_question(user_input.strip())
