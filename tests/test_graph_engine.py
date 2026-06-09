"""
tests/test_graph_engine.py
──────────────────────────
Tests for graph_engine:
  • Column classification heuristics
  • SQLite register_file idempotency
  • Within-file relationship detection (correlation, co_occurrence)
  • Cross-file shared_name relationship detection
  • GraphMeta structure
  • Plotly figure construction
"""

from __future__ import annotations

import os
import tempfile

import numpy as np
import pandas as pd
import pytest

from graph_engine import (
    GraphMeta,
    _classify_column,
    _cramers_v,
    build_plotly_graph,
    load_full_graph,
    register_file,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path) -> str:
    return str(tmp_path / "test.db")


@pytest.fixture
def sales_df() -> pd.DataFrame:
    rng = np.random.default_rng(0)
    n = 60
    df = pd.DataFrame({
        "order_id":  range(1, n + 1),
        "region":    rng.choice(["North", "South", "East"], n),
        "product":   rng.choice(["A", "B", "C"], n),
        "quantity":  rng.integers(1, 20, n),
        "revenue":   np.round(rng.uniform(100, 5000, n), 2),
        "date":      pd.date_range("2024-01-01", periods=n, freq="D"),
    })
    df["revenue"] = df["quantity"] * 100.0  # perfect correlation with quantity
    return df


@pytest.fixture
def customers_df() -> pd.DataFrame:
    """DataFrame sharing 'region' column name with sales_df."""
    rng = np.random.default_rng(1)
    n = 30
    return pd.DataFrame({
        "customer_id": range(100, 100 + n),
        "region":      rng.choice(["North", "South", "East"], n),
        "age":         rng.integers(18, 70, n),
    })


# ── Column classification ─────────────────────────────────────────────────────

def test_classify_datetime():
    s = pd.Series(pd.date_range("2024-01-01", periods=10))
    col_type, is_entity, is_id = _classify_column("event_date", s)
    assert col_type == "datetime"
    assert not is_entity


def test_classify_high_cardinality_string():
    s = pd.Series([f"unique_{i}" for i in range(100)])
    col_type, is_entity, is_id = _classify_column("description", s)
    assert col_type == "text"
    assert not is_entity


def test_classify_low_cardinality_string():
    s = pd.Series(["North", "South", "East"] * 20)
    col_type, is_entity, is_id = _classify_column("region", s)
    assert col_type == "entity"
    assert is_entity


def test_classify_id_column():
    s = pd.Series(range(1, 101))
    col_type, is_entity, is_id = _classify_column("order_id", s)
    assert is_id


def test_classify_numeric_few_unique():
    s = pd.Series([1, 2, 3] * 30)
    col_type, is_entity, is_id = _classify_column("rating", s)
    assert col_type == "entity"
    assert is_entity


def test_classify_numeric_many_unique():
    s = pd.Series(np.random.default_rng(0).uniform(0, 1000, 200))
    col_type, is_entity, is_id = _classify_column("revenue", s)
    assert col_type == "numeric"
    assert not is_entity


# ── Cramer's V ────────────────────────────────────────────────────────────────

def test_cramers_v_identical_columns():
    s = pd.Series(["A", "B", "C"] * 20)
    v = _cramers_v(s, s)
    assert v > 0.9


def test_cramers_v_independent_columns():
    rng = np.random.default_rng(42)
    s1 = pd.Series(rng.choice(["X", "Y"], 100))
    s2 = pd.Series(rng.choice(["P", "Q"], 100))
    v = _cramers_v(s1, s2)
    assert v < 0.3  # should be close to 0 for independent variables


# ── register_file ─────────────────────────────────────────────────────────────

def test_register_file_returns_graph_meta(sales_df, tmp_db):
    meta = register_file("sales.xlsx", sales_df, "Sheet1", tmp_db)
    assert isinstance(meta, GraphMeta)
    assert len(meta.nodes) == len(sales_df.columns)
    assert meta.file_name == "sales.xlsx"


def test_register_file_detects_nodes(sales_df, tmp_db):
    meta = register_file("sales.xlsx", sales_df, db_path=tmp_db)
    labels = [n["label"] for n in meta.nodes]
    for col in sales_df.columns:
        assert str(col) in labels


def test_register_file_detects_correlation(sales_df, tmp_db):
    """revenue = quantity * 100 → perfect correlation → edge should be detected."""
    meta = register_file("sales.xlsx", sales_df, db_path=tmp_db)
    corr_edges = [e for e in meta.edges if e["rel"] == "correlation"]
    # quantity↔revenue must be in edges (r ≈ 1.0)
    edge_labels = {(e["source"].split("::")[-1], e["target"].split("::")[-1]) for e in corr_edges}
    edge_labels |= {(b, a) for a, b in edge_labels}
    assert ("quantity", "revenue") in edge_labels or ("revenue", "quantity") in edge_labels


def test_register_file_idempotent(sales_df, tmp_db):
    """Registering the same file twice should not duplicate nodes."""
    register_file("sales.xlsx", sales_df, db_path=tmp_db)
    meta2 = register_file("sales.xlsx", sales_df, db_path=tmp_db)
    node_labels = [n["label"] for n in meta2.nodes]
    # No duplicate labels for same file
    assert len(node_labels) == len(set(node_labels))


# ── Cross-file shared_name ────────────────────────────────────────────────────

def test_shared_name_detected(sales_df, customers_df, tmp_db):
    """'region' appears in both files → shared_name edge expected."""
    register_file("sales.xlsx", sales_df, db_path=tmp_db)
    meta2 = register_file("customers.xlsx", customers_df, db_path=tmp_db)

    full = load_full_graph(tmp_db)
    shared = [e for e in full.edges if e["rel"] == "shared_name"]
    shared_labels = {e["source"].split("::")[-1] for e in shared}
    shared_labels |= {e["target"].split("::")[-1] for e in shared}
    assert "region" in shared_labels


# ── load_full_graph ───────────────────────────────────────────────────────────

def test_load_full_graph_empty(tmp_db):
    meta = load_full_graph(tmp_db)
    assert isinstance(meta, GraphMeta)
    assert meta.nodes == []
    assert meta.edges == []


def test_load_full_graph_has_all_files(sales_df, customers_df, tmp_db):
    register_file("sales.xlsx", sales_df, db_path=tmp_db)
    register_file("customers.xlsx", customers_df, db_path=tmp_db)
    full = load_full_graph(tmp_db)
    files_in_graph = {n["file"] for n in full.nodes}
    assert "sales.xlsx" in files_in_graph
    assert "customers.xlsx" in files_in_graph


# ── build_plotly_graph ────────────────────────────────────────────────────────

def test_build_plotly_graph_returns_figure(sales_df, tmp_db):
    import plotly.graph_objects as go
    meta = register_file("sales.xlsx", sales_df, db_path=tmp_db)
    fig = build_plotly_graph(meta)
    assert isinstance(fig, go.Figure)


def test_build_plotly_graph_empty_meta():
    import plotly.graph_objects as go
    empty_meta = GraphMeta(nodes=[], edges=[], file_name="empty", sheet_name="")
    fig = build_plotly_graph(empty_meta)
    assert isinstance(fig, go.Figure)
