"""
tests/test_insight_engine.py
────────────────────────────
Tests for insight_engine.profile_dataframe():
  • DataProfile shape and metadata
  • Missing value counts
  • IQR outlier detection
  • Correlation matrix accuracy
  • Top correlated pairs ordering
  • Categorical value counts
  • Time series detection
  • Statistical summary text
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from insight_engine import DataProfile, profile_dataframe


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def minimal_df() -> pd.DataFrame:
    """4-row DataFrame: outlier in 'a', missing in 'b', categorical 'cat'."""
    return pd.DataFrame({
        "a":   [1.0, 2.0, 3.0, 100.0],
        "b":   [4.0, None, 6.0, 7.0],
        "cat": ["x", "y", "x", "z"],
    })


@pytest.fixture
def corr_df() -> pd.DataFrame:
    """Two perfectly correlated numeric columns."""
    x = np.arange(10, dtype=float)
    return pd.DataFrame({"x": x, "y": x * 2.0, "z": x[::-1]})


@pytest.fixture
def ts_df() -> pd.DataFrame:
    """DataFrame with a date column for time-series detection."""
    dates = pd.date_range("2023-01-01", periods=24, freq="M")
    rng = np.random.default_rng(1)
    return pd.DataFrame({
        "date":    dates,
        "revenue": rng.uniform(1000, 9000, 24).round(2),
    })


# ── Basic shape and metadata ──────────────────────────────────────────────────

def test_profile_shape(minimal_df):
    p = profile_dataframe(minimal_df, "test.csv", "Sheet1")
    assert p.n_rows == 4
    assert p.n_cols == 3
    assert p.file_name == "test.csv"
    assert p.sheet_name == "Sheet1"


def test_profile_column_classification(minimal_df):
    p = profile_dataframe(minimal_df)
    assert "a" in p.numeric_cols
    assert "b" in p.numeric_cols
    assert "cat" in p.categorical_cols
    assert len(p.date_cols) == 0


# ── Missing values ────────────────────────────────────────────────────────────

def test_missing_counts(minimal_df):
    p = profile_dataframe(minimal_df)
    assert int(p.missing_counts["b"]) == 1
    assert int(p.missing_counts["a"]) == 0
    assert int(p.missing_counts["cat"]) == 0


def test_missing_pct(minimal_df):
    p = profile_dataframe(minimal_df)
    # 1 missing out of 4 rows = 25%
    assert abs(p.missing_pct["b"] - 25.0) < 0.01


# ── Outlier detection ─────────────────────────────────────────────────────────

def test_iqr_outlier_detected(minimal_df):
    p = profile_dataframe(minimal_df)
    # a=[1,2,3,100]: Q1=1.75, Q3=3.75 → IQR=2, upper fence=6.75 → 100 is outlier
    assert "a" in p.outlier_counts
    assert p.outlier_counts["a"] >= 1


def test_no_outlier_in_uniform(numeric_df):
    p = profile_dataframe(numeric_df)
    # Linearly spaced data has no IQR outliers
    for col in p.numeric_cols:
        assert p.outlier_counts.get(col, 0) == 0


# ── Correlation ───────────────────────────────────────────────────────────────

def test_correlation_matrix_shape(corr_df):
    p = profile_dataframe(corr_df)
    assert p.corr_matrix is not None
    assert p.corr_matrix.shape == (3, 3)


def test_perfect_positive_correlation(corr_df):
    p = profile_dataframe(corr_df)
    # x and y are perfectly correlated
    r_xy = p.corr_matrix.loc["x", "y"]
    assert abs(r_xy - 1.0) < 1e-6


def test_perfect_negative_correlation(corr_df):
    p = profile_dataframe(corr_df)
    # x and z are perfectly negatively correlated
    r_xz = p.corr_matrix.loc["x", "z"]
    assert abs(r_xz + 1.0) < 1e-6


def test_top_corr_pairs_ordered(corr_df):
    p = profile_dataframe(corr_df)
    # Pairs should be sorted by abs(r) descending
    strengths = [abs(r) for _, _, r in p.top_corr_pairs]
    assert strengths == sorted(strengths, reverse=True)


def test_no_corr_matrix_for_single_numeric(minimal_df):
    """Only one numeric column should yield None for corr_matrix."""
    single = pd.DataFrame({"a": [1, 2, 3], "cat": ["x", "y", "z"]})
    p = profile_dataframe(single)
    assert p.corr_matrix is None


# ── Categorical value counts ──────────────────────────────────────────────────

def test_value_counts_present(minimal_df):
    p = profile_dataframe(minimal_df)
    assert "cat" in p.value_counts
    vc = p.value_counts["cat"]
    assert vc["x"] == 2   # "x" appears twice
    assert vc["y"] == 1


def test_value_counts_top20(sample_df):
    """Value counts should be capped at 20."""
    p = profile_dataframe(sample_df)
    for vc in p.value_counts.values():
        assert len(vc) <= 20


# ── Time series detection ─────────────────────────────────────────────────────

def test_time_series_detected(ts_df):
    p = profile_dataframe(ts_df, sheet_name="ts")
    assert "date" in p.date_cols
    # Monthly resampling of 24 months should produce entries
    if "date" in p.time_series:
        ts = p.time_series["date"]
        assert len(ts) >= 2


def test_no_time_series_without_date_cols(minimal_df):
    p = profile_dataframe(minimal_df)
    assert p.date_cols == []
    assert p.time_series == {}


# ── Statistical summary ───────────────────────────────────────────────────────

def test_statistical_summary_contains_shape(minimal_df):
    p = profile_dataframe(minimal_df, "f.csv")
    assert "4" in p.statistical_summary   # row count
    assert "3" in p.statistical_summary   # col count


def test_statistical_summary_is_string(minimal_df):
    p = profile_dataframe(minimal_df)
    assert isinstance(p.statistical_summary, str)
    assert len(p.statistical_summary) > 10
