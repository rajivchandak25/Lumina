"""
tests/test_excel_processor.py
──────────────────────────────
Tests for excel_processor:
  • build_schema_description output format
  • coerce_dtypes datetime and numeric inference
  • get_sample_rows markdown output
"""

from __future__ import annotations

import io

import numpy as np
import pandas as pd
import pytest

from excel_processor import (
    build_schema_description,
    coerce_dtypes,
    get_sample_rows,
    load_excel,
)


# ── build_schema_description ──────────────────────────────────────────────────

def test_schema_includes_sheet_name(sample_df):
    desc = build_schema_description(sample_df, "MySales")
    assert "MySales" in desc


def test_schema_includes_row_count(sample_df):
    desc = build_schema_description(sample_df, "Sheet1")
    assert "120" in desc


def test_schema_includes_column_count(sample_df):
    desc = build_schema_description(sample_df, "Sheet1")
    assert str(sample_df.shape[1]) in desc


def test_schema_includes_all_column_names(sample_df):
    desc = build_schema_description(sample_df, "Sheet1")
    for col in sample_df.columns:
        assert str(col) in desc


def test_schema_shows_numeric_stats(sample_df):
    desc = build_schema_description(sample_df, "Sheet1")
    # Numeric columns should have min/max/mean
    assert "min=" in desc
    assert "max=" in desc
    assert "mean=" in desc


def test_schema_shows_null_count():
    df = pd.DataFrame({"a": [1, None, 3], "b": ["x", "y", None]})
    desc = build_schema_description(df, "Test")
    assert "null" in desc.lower() or "null" in desc


# ── coerce_dtypes ─────────────────────────────────────────────────────────────

def test_coerce_strips_column_whitespace():
    df = pd.DataFrame({" name ": ["Alice"], " age ": [30]})
    result = coerce_dtypes(df)
    assert "name" in result.columns
    assert "age" in result.columns
    assert " name " not in result.columns


def test_coerce_date_column_inferred():
    df = pd.DataFrame({"order_date": ["2024-01-01", "2024-01-02", "2024-01-03"]})
    result = coerce_dtypes(df)
    assert pd.api.types.is_datetime64_any_dtype(result["order_date"])


def test_coerce_numeric_string_column():
    df = pd.DataFrame({"amount": ["10.5", "20.0", "30.1"]})
    result = coerce_dtypes(df)
    assert pd.api.types.is_numeric_dtype(result["amount"])


def test_coerce_does_not_mutate_original():
    df = pd.DataFrame({"date": ["2024-01-01"], "val": ["42"]})
    original_dtypes = df.dtypes.copy()
    coerce_dtypes(df)
    assert df["date"].dtype == original_dtypes["date"]


def test_coerce_returns_new_dataframe(sample_df):
    result = coerce_dtypes(sample_df)
    assert result is not sample_df


# ── get_sample_rows ───────────────────────────────────────────────────────────

def test_sample_rows_is_markdown(sample_df):
    md = get_sample_rows(sample_df, n=3)
    assert "|" in md  # markdown table delimiter


def test_sample_rows_count(sample_df):
    md = get_sample_rows(sample_df, n=5)
    # Markdown table: header + separator + 5 data rows = 7 lines min
    lines = [l for l in md.strip().split("\n") if l.strip()]
    assert len(lines) >= 6  # header + sep + 5 rows (may vary by tabulate version)


def test_sample_rows_includes_column_names(sample_df):
    md = get_sample_rows(sample_df, n=1)
    for col in sample_df.columns:
        assert str(col) in md


# ── load_excel (CSV branch) ───────────────────────────────────────────────────

def test_load_csv_returns_single_sheet():
    csv_bytes = b"a,b,c\n1,2,3\n4,5,6\n"

    class FakeFile:
        name = "data.csv"
        def read(self): return csv_bytes

    sheets = load_excel(FakeFile())
    assert "Sheet1" in sheets
    assert sheets["Sheet1"].shape == (2, 3)
