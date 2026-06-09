"""
tests/test_code_executor.py
───────────────────────────
Tests for CodeExecutor: result type classification, sandbox security,
plotly support, self-healing compatibility.
"""

from __future__ import annotations

import pandas as pd
import pytest

from code_executor import CodeExecutor


@pytest.fixture
def ex() -> CodeExecutor:
    return CodeExecutor()


@pytest.fixture
def df() -> pd.DataFrame:
    return pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})


# ── Result types ──────────────────────────────────────────────────────────────

def test_scalar_result(ex, df):
    out = ex.run("result = 42", df)
    assert out.success
    assert out.result_type == "scalar"
    assert out.result == 42


def test_text_result(ex, df):
    out = ex.run("result = 'hello'", df)
    assert out.success
    assert out.result_type == "text"
    assert out.result == "hello"


def test_dataframe_result(ex, df):
    out = ex.run("result = df.head(2)", df)
    assert out.success
    assert out.result_type == "dataframe"
    assert len(out.result) == 2


def test_none_result(ex, df):
    out = ex.run("x = 1", df)
    assert out.success
    # No `result` variable → type is "none" OR last open figure (if any)
    # In either case, success should be True
    assert out.result_type in ("none", "figure")


def test_axes_normalized_to_figure(ex, df):
    """LLM returning result=ax should be normalized to Figure."""
    code = "fig, ax = plt.subplots()\nax.plot([1, 2, 3], [1, 4, 9])\nresult = ax"
    out = ex.run(code, df)
    assert out.success
    assert out.result_type == "figure"


def test_matplotlib_figure_result(ex, df):
    code = "fig, ax = plt.subplots()\nax.bar(['A','B','C'],[1,2,3])\nresult = fig"
    out = ex.run(code, df)
    assert out.success
    assert out.result_type == "figure"


def test_plotly_figure_result(ex, df):
    """Plotly Figure should be classified as result_type='plotly'."""
    code = "result = px.bar(df, x='a', y='b', title='Test')"
    out = ex.run(code, df)
    assert out.success, f"Failed: {out.error}"
    assert out.result_type == "plotly"


def test_plotly_figure_dark_theme(ex, df):
    """Plotly figure with dark layout should still classify correctly."""
    code = (
        "fig = px.bar(df, x='a', y='b')\n"
        "fig.update_layout(template='plotly_dark', paper_bgcolor='#0d1117')\n"
        "result = fig"
    )
    out = ex.run(code, df)
    assert out.success
    assert out.result_type == "plotly"


# ── DataFrame is never mutated ────────────────────────────────────────────────

def test_original_df_not_mutated(ex):
    original = pd.DataFrame({"x": [1, 2, 3]})
    ex.run("df['new_col'] = 99", original)
    assert "new_col" not in original.columns


# ── Static security checks ────────────────────────────────────────────────────

def test_blocked_import_os(ex, df):
    out = ex.run("import os\nresult = os.getcwd()", df)
    assert not out.success
    assert "Blocked import" in (out.error or "")


def test_blocked_import_sys(ex, df):
    out = ex.run("import sys\nresult = sys.version", df)
    assert not out.success
    assert "Blocked import" in (out.error or "")


def test_blocked_import_subprocess(ex, df):
    out = ex.run("import subprocess\nresult = 'bad'", df)
    assert not out.success


def test_blocked_from_import(ex, df):
    out = ex.run("from os.path import join\nresult = join('a', 'b')", df)
    assert not out.success
    assert "Blocked import" in (out.error or "")


def test_blocked_eval_call(ex, df):
    out = ex.run("result = eval('1+1')", df)
    assert not out.success
    assert "Blocked function call" in (out.error or "")


def test_blocked_exec_call(ex, df):
    out = ex.run("exec('x=1')\nresult = 1", df)
    assert not out.success


def test_syntax_error_reported(ex, df):
    out = ex.run("def broken(\nresult = 1", df)
    assert not out.success
    assert "Syntax error" in (out.error or "") or "SyntaxError" in (out.error or "")


# ── Stdout capture ────────────────────────────────────────────────────────────

def test_stdout_captured(ex, df):
    out = ex.run("print('hello world')\nresult = 1", df)
    assert out.success
    assert "hello world" in out.stdout


# ── Legitimate operations ─────────────────────────────────────────────────────

def test_numpy_available(ex, df):
    out = ex.run("result = float(np.mean(df['a']))", df)
    assert out.success
    assert out.result_type == "scalar"
    assert abs(out.result - 2.0) < 1e-6


def test_pandas_groupby(ex):
    data = pd.DataFrame({"cat": ["A", "A", "B"], "val": [10, 20, 30]})
    out = ex.run("result = df.groupby('cat')['val'].sum().reset_index()", data)
    assert out.success
    assert out.result_type == "dataframe"
    assert len(out.result) == 2
