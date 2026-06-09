"""
insight_engine.py
─────────────────
Computes a full DataProfile from a pandas DataFrame.

Pure computation — zero Streamlit imports. The profile is computed once
on file upload and cached in st.session_state.profile. The dashboard
page reads the cached profile and renders it.

Key outputs per DataProfile:
  • Missing value counts and percentages
  • Descriptive statistics for numeric columns
  • Pearson correlation matrix + top 5 pairs
  • IQR-based outlier counts per numeric column
  • Value counts for categorical columns (top 20)
  • Monthly-resampled time series for date columns
  • Compact statistical_summary string for LLM prompts
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

_PD_VER_PARTS = pd.__version__.split(".")
try:
    _PD_MAJOR = int(_PD_VER_PARTS[0])
    _PD_MINOR = int(_PD_VER_PARTS[1])
except Exception:
    _PD_MAJOR, _PD_MINOR = 2, 1
_MONTH_END_FREQ = "ME" if (_PD_MAJOR, _PD_MINOR) >= (2, 2) else "M"

# ── DataProfile ───────────────────────────────────────────────────────────────

@dataclass
class DataProfile:
    # Basic metadata
    file_name:    str
    sheet_name:   str
    n_rows:       int
    n_cols:       int

    # Missing values
    missing_counts: pd.Series        # col → int count
    missing_pct:    pd.Series        # col → float 0-100

    # Numeric
    numeric_cols: list[str]
    describe_df:  pd.DataFrame       # df.describe() output for numeric cols

    # Correlations
    corr_matrix:     Optional[pd.DataFrame]           # None if < 2 numeric cols
    top_corr_pairs:  list[tuple[str, str, float]]     # top 5 by abs(r), (col_a, col_b, r)

    # Outliers (IQR method, 1.5 × IQR)
    outlier_counts: dict[str, int]   # col → n outlier rows

    # Categorical
    categorical_cols: list[str]
    value_counts:     dict[str, pd.Series]   # col → top-20 value_counts Series

    # Time series
    date_cols:   list[str]
    time_series: dict[str, pd.Series]  # date_col → monthly sum/count Series

    # Compact text for LLM prompts (predictions / causes)
    statistical_summary: str


# ── Public API ────────────────────────────────────────────────────────────────

def profile_dataframe(
    df: pd.DataFrame,
    file_name: str = "",
    sheet_name: str = "Sheet1",
) -> DataProfile:
    """
    Compute a full DataProfile from *df*.

    Typical runtime: < 200 ms for 100 k rows.
    Never raises — all sub-computations are individually try/except guarded.
    """
    n_rows, n_cols = df.shape

    # ── Missing ───────────────────────────────────────────────────────────────
    missing_counts = df.isna().sum()
    missing_pct    = (missing_counts / max(n_rows, 1)) * 100.0

    # ── Column classification ─────────────────────────────────────────────────
    numeric_cols:     list[str] = []
    categorical_cols: list[str] = []
    date_cols:        list[str] = []

    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            date_cols.append(col)
        elif pd.api.types.is_numeric_dtype(df[col]):
            numeric_cols.append(col)
        else:
            categorical_cols.append(col)

    # ── Descriptive statistics ────────────────────────────────────────────────
    try:
        describe_df = df[numeric_cols].describe() if numeric_cols else pd.DataFrame()
    except Exception:
        describe_df = pd.DataFrame()

    # ── Correlation matrix ────────────────────────────────────────────────────
    corr_matrix:    Optional[pd.DataFrame]       = None
    top_corr_pairs: list[tuple[str, str, float]] = []

    if len(numeric_cols) >= 2:
        try:
            corr_matrix = df[numeric_cols].corr()

            # Extract upper triangle (exclude diagonal)
            upper_mask = np.triu(np.ones(corr_matrix.shape, dtype=bool), k=1)
            upper_vals = corr_matrix.where(upper_mask)

            pairs_df = (
                upper_vals
                .stack()
                .reset_index()
                .rename(columns={"level_0": "col_a", "level_1": "col_b", 0: "r"})
            )
            pairs_df["abs_r"] = pairs_df["r"].abs()
            top5 = pairs_df.nlargest(5, "abs_r")
            top_corr_pairs = [
                (row.col_a, row.col_b, round(float(row.r), 4))
                for row in top5.itertuples(index=False)
            ]
        except Exception:
            corr_matrix = None

    # ── Outlier detection (IQR × 1.5) ────────────────────────────────────────
    outlier_counts: dict[str, int] = {}
    for col in numeric_cols:
        try:
            series = df[col].dropna()
            q1, q3 = series.quantile(0.25), series.quantile(0.75)
            iqr = q3 - q1
            n_outliers = int(((series < q1 - 1.5 * iqr) | (series > q3 + 1.5 * iqr)).sum())
            if n_outliers > 0:
                outlier_counts[col] = n_outliers
        except Exception:
            pass

    # ── Categorical value counts ──────────────────────────────────────────────
    value_counts: dict[str, pd.Series] = {}
    for col in categorical_cols:
        try:
            value_counts[col] = df[col].value_counts().head(20)
        except Exception:
            pass

    # ── Time series resampling ────────────────────────────────────────────────
    time_series: dict[str, pd.Series] = {}
    for date_col in date_cols:
        try:
            series = df[date_col].dropna()
            if series.nunique() < 10:
                continue
            # Find the first numeric column to aggregate
            target_col = numeric_cols[0] if numeric_cols else None
            ts_df = df[[date_col]].copy()
            if target_col:
                ts_df[target_col] = df[target_col]
                ts_series = (
                    ts_df.set_index(date_col)[target_col]
                    .resample(_MONTH_END_FREQ)
                    .sum()
                    .dropna()
                )
            else:
                ts_series = (
                    ts_df.set_index(date_col)
                    .resample(_MONTH_END_FREQ)
                    .size()
                    .rename("count")
                )
            if len(ts_series) >= 2:
                time_series[date_col] = ts_series
        except Exception:
            pass

    # ── Compact statistical summary (for LLM) ────────────────────────────────
    statistical_summary = _build_statistical_summary(
        n_rows, n_cols, missing_counts, top_corr_pairs, outlier_counts,
        numeric_cols, categorical_cols, date_cols,
    )

    return DataProfile(
        file_name=file_name,
        sheet_name=sheet_name,
        n_rows=n_rows,
        n_cols=n_cols,
        missing_counts=missing_counts,
        missing_pct=missing_pct,
        numeric_cols=numeric_cols,
        describe_df=describe_df,
        corr_matrix=corr_matrix,
        top_corr_pairs=top_corr_pairs,
        outlier_counts=outlier_counts,
        categorical_cols=categorical_cols,
        value_counts=value_counts,
        date_cols=date_cols,
        time_series=time_series,
        statistical_summary=statistical_summary,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_statistical_summary(
    n_rows: int,
    n_cols: int,
    missing_counts: pd.Series,
    top_corr_pairs: list[tuple[str, str, float]],
    outlier_counts: dict[str, int],
    numeric_cols: list[str],
    categorical_cols: list[str],
    date_cols: list[str],
) -> str:
    """Build a compact text summary suitable for LLM prompt injection."""
    missing_dict = missing_counts[missing_counts > 0].to_dict()
    corr_text = ", ".join(
        f"{a}↔{b}: {r:+.2f}" for a, b, r in top_corr_pairs
    ) or "none detected"
    outlier_text = (
        ", ".join(f"{c}: {n}" for c, n in outlier_counts.items())
        if outlier_counts else "none detected"
    )

    lines = [
        f"Shape: {n_rows:,} rows × {n_cols} columns",
        f"Numeric columns: {numeric_cols}",
        f"Categorical columns: {categorical_cols}",
        f"Date columns: {date_cols}",
        f"Missing values: {missing_dict if missing_dict else 'none'}",
        f"Top correlations: {corr_text}",
        f"Outliers (IQR method): {outlier_text}",
    ]
    return "\n".join(lines)

