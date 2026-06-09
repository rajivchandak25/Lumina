"""
export_utils.py
───────────────
Export helpers for Lumina:
  • Markdown transcript of the full chat history
  • Excel workbook with all DataFrame results (one sheet per result)
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    pass


# ── Public API ────────────────────────────────────────────────────────────────

def export_chat_markdown(chat_history: list[dict], file_name: str | None = None) -> str:
    """
    Build a Markdown transcript of *chat_history* suitable for download.

    Parameters
    ----------
    chat_history : list[dict]   Internal history: [{"role", "content", "extra"}]
    file_name    : str | None   Source filename shown in the header.
    """
    fn = file_name or "dataset"
    lines = [
        "# Lumina transcript",
        "",
        f"- **File:** `{fn}`",
        f"- **Exported:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "---",
        "",
    ]
    for turn in chat_history:
        if turn["role"] == "user":
            lines.extend(["## You", "", turn.get("content", "").strip(), "", "---", ""])
        else:
            lines.extend(["## Assistant", "", turn.get("content", "").strip(), ""])
            ex = turn.get("extra") or {}
            if ex.get("code"):
                lines.extend(["", "```python", ex["code"].rstrip(), "```", ""])
            if ex.get("dataframe") is not None:
                lines.append("*[Table result — see app UI for full data.]*\n")
            if ex.get("figure_bytes") or ex.get("plotly_figure") is not None:
                lines.append("*[Chart — see app UI.]*\n")
            lines.extend(["", "---", ""])
    return "\n".join(lines).rstrip() + "\n"


def export_results_to_xlsx(chat_history: list[dict]) -> bytes:
    """
    Collect every DataFrame result from *chat_history* and write each
    to a separate sheet in an .xlsx workbook.

    Returns bytes suitable for ``st.download_button``.
    Sheet names: Result_1, Result_2, …

    Returns a workbook with a single placeholder sheet if there are no
    DataFrame results (so the download never fails).
    """
    buf = io.BytesIO()
    results: list[pd.DataFrame] = []
    for turn in chat_history:
        if turn.get("role") == "assistant":
            df_result = (turn.get("extra") or {}).get("dataframe")
            if isinstance(df_result, pd.DataFrame):
                results.append(df_result)

    engine = "xlsxwriter"
    try:
        import xlsxwriter  # noqa: F401
    except Exception:
        engine = "openpyxl"

    with pd.ExcelWriter(buf, engine=engine) as writer:
        if results:
            for i, df in enumerate(results, start=1):
                sheet_name = f"Result_{i}"
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                # Auto-fit column widths (best-effort)
                worksheet = writer.sheets[sheet_name]
                if engine == "xlsxwriter":
                    for col_idx, col in enumerate(df.columns):
                        max_len = max(len(str(col)), df[col].astype(str).str.len().max() if len(df) else 0)
                        worksheet.set_column(col_idx, col_idx, min(max_len + 2, 50))
        else:
            pd.DataFrame({"Note": ["No table results in this conversation."]}).to_excel(
                writer, sheet_name="Info", index=False
            )

    return buf.getvalue()
