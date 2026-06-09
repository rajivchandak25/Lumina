"""
excel_processor.py
──────────────────
Handles loading and introspecting Excel / CSV files into Pandas DataFrames.

Responsibilities:
  • Read uploaded Streamlit file objects into DataFrames
  • Detect multiple sheets and let the caller choose
  • Build a rich, LLM-friendly schema description of the loaded data
  • Provide a clean sample of the data for the LLM prompt
"""

from __future__ import annotations

import io
from typing import Optional

import numpy as np
import pandas as pd


# ── Public API ────────────────────────────────────────────────────────────────

def load_excel(file_obj) -> dict[str, pd.DataFrame]:
    """
    Load an uploaded file (Excel or CSV) and return a dict mapping
    sheet-name → DataFrame.

    Supports .xlsx, .xls (via xlrd) and .csv files.
    """
    filename: str = getattr(file_obj, "name", "upload")
    if hasattr(file_obj, "getvalue"):
        raw_bytes = file_obj.getvalue()
    else:
        raw_bytes = file_obj.read()
    buf = io.BytesIO(raw_bytes)

    if filename.lower().endswith(".csv"):
        df = pd.read_csv(buf)
        return {"Sheet1": df}

    # Excel — read all sheets at once
    sheets: dict[str, pd.DataFrame] = pd.read_excel(
        buf,
        sheet_name=None,   # None → all sheets
        engine=_pick_engine(filename),
    )
    return sheets


def build_schema_description(df: pd.DataFrame, sheet_name: str = "Sheet1") -> str:
    """
    Produce a compact, human-readable schema string that is inserted into the
    Gemini prompt so the model knows exactly what data it is working with.

    Example output:
        Sheet: Sales_Data
        Rows: 1 200  |  Columns: 8
        Columns:
          • Date        (datetime64[ns])  — e.g. 2023-01-01
          • Region      (object)          — e.g. North, South, East  (4 unique)
          • Revenue     (float64)         — min=120.5  max=98 000.0  mean=12 345.6
          ...
    """
    lines: list[str] = [
        f"Sheet: {sheet_name}",
        f"Rows: {len(df):,}  |  Columns: {df.shape[1]}",
        "Columns:",
    ]

    for col in df.columns:
        dtype = str(df[col].dtype)
        n_null = int(df[col].isna().sum())
        null_note = f"  ({n_null} nulls)" if n_null else ""

        if pd.api.types.is_numeric_dtype(df[col]):
            desc = (
                f"min={df[col].min():.4g}  "
                f"max={df[col].max():.4g}  "
                f"mean={df[col].mean():.4g}"
            )
        elif pd.api.types.is_datetime64_any_dtype(df[col]):
            desc = f"range {df[col].min().date()} → {df[col].max().date()}"
        else:
            # Categorical / text column — show sample unique values
            uniques = df[col].dropna().unique()
            sample = ", ".join(str(v) for v in uniques[:5])
            if len(uniques) > 5:
                sample += f"…  ({len(uniques)} unique)"
            desc = f"e.g. {sample}"

        lines.append(f"  • {col:<25} ({dtype}){null_note}  — {desc}")

    return "\n".join(lines)


def get_sample_rows(df: pd.DataFrame, n: int = 5) -> str:
    """Return the first *n* rows as a compact markdown table for the prompt."""
    return df.head(n).to_markdown(index=False)


def coerce_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Best-effort dtype coercion:
      • Strip whitespace from column names
      • Columns whose name contains 'date' / 'time' → datetime
      • Pure-numeric object columns → numeric
    Returns a new DataFrame with improved dtypes.
    """
    df = df.copy()
    
    # Strip whitespace from string column names
    df.columns = [col.strip() if isinstance(col, str) else col for col in df.columns]

    for col in df.columns:
        col_lower = str(col).lower()
        if any(kw in col_lower for kw in ("date", "time", "dt", "month", "year")):
            try:
                df[col] = pd.to_datetime(df[col], format="mixed")
            except Exception:
                pass
        else:
            try:
                df[col] = pd.to_numeric(df[col])
            except Exception:
                pass
    return df


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pick_engine(filename: str) -> Optional[str]:
    """Return the correct openpyxl/xlrd engine for the file extension."""
    if filename.lower().endswith(".xls"):
        return "xlrd"
    return "openpyxl"
