"""
code_executor.py
────────────────
Safe execution of LLM-generated Python code in a restricted sandbox.

Security model
──────────────
The generated code is executed with a highly restricted ``__builtins__``
dict that contains only a safe allow-list of built-in names.
All dangerous modules (os, sys, subprocess, shutil, socket …) are
absent from the execution namespace.

The executor also performs a static *pre-scan* of the code string before
running it to catch obvious attempts to import blocked modules or call
known dangerous functions.

This is NOT a fully hardened sandbox (no seccomp, no containers), but it
is appropriate for a trusted internal / demo tool where we control the
code source (a Gemini prompt with strict system instructions).

Returns
───────
ExecutionResult(success, result, error, result_type, stdout)
  result_type ∈ {"dataframe", "figure", "plotly", "scalar", "text", "none"}
"""

from __future__ import annotations

import ast
import io
import textwrap
import traceback
from dataclasses import dataclass, field
from typing import Any, Optional

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

matplotlib.use("Agg")  # non-interactive backend — safe for server use


# ── Result container ──────────────────────────────────────────────────────────

@dataclass
class ExecutionResult:
    success: bool
    result: Any = None
    error: Optional[str] = None
    result_type: str = "none"   # "dataframe" | "figure" | "plotly" | "scalar" | "text" | "none"
    stdout: str = ""


# ── Blocked patterns (pre-execution static check) ─────────────────────────────

_BLOCKED_IMPORTS: frozenset[str] = frozenset({
    "os", "sys", "subprocess", "shutil", "socket", "requests", "urllib",
    "http", "ftplib", "smtplib", "pickle", "shelve", "sqlite3",
    "threading", "multiprocessing", "ctypes", "cffi", "importlib",
    "builtins", "__import__", "globals", "locals", "vars", "dir",
})

_BLOCKED_CALLS: frozenset[str] = frozenset({
    "exec", "eval", "compile", "__import__", "open",
    "input", "print",   # print is not dangerous but we capture stdout separately
})


# ── Safe builtins allow-list ──────────────────────────────────────────────────

_SAFE_BUILTINS: dict[str, Any] = {
    name: __builtins__[name] if isinstance(__builtins__, dict) else getattr(__builtins__, name)
    for name in (
        "abs", "all", "any", "bin", "bool", "chr", "dict", "divmod",
        "enumerate", "filter", "float", "format", "frozenset", "getattr",
        "hasattr", "hash", "hex", "int", "isinstance", "issubclass",
        "iter", "len", "list", "map", "max", "min", "next", "oct",
        "ord", "pow", "print", "range", "repr", "reversed", "round",
        "set", "slice", "sorted", "str", "sum", "tuple", "type", "zip",
        "True", "False", "None",
        "ValueError", "TypeError", "KeyError", "IndexError",
        "AttributeError", "Exception", "RuntimeError", "StopIteration",
        "NotImplementedError", "ArithmeticError", "ZeroDivisionError",
    )
    if (isinstance(__builtins__, dict) and name in __builtins__)
    or (not isinstance(__builtins__, dict) and hasattr(__builtins__, name))
}


# ── Public API ────────────────────────────────────────────────────────────────

class CodeExecutor:
    """Executes LLM-generated Pandas/Plotly code safely and returns a typed result."""

    def run(self, code: str, df: pd.DataFrame) -> ExecutionResult:
        """
        Execute *code* in a sandboxed namespace that has access to *df*.

        Parameters
        ----------
        code : str           Python code string from the LLM.
        df   : pd.DataFrame  The user's loaded data.

        Returns
        -------
        ExecutionResult
        """
        # 1. Static safety check
        violation = _static_check(code)
        if violation:
            return ExecutionResult(
                success=False,
                error=f"Security violation detected: {violation}\n\nCode was not executed.",
            )

        # 2. Isolate matplotlib state so previous runs don't leak figures
        plt.close("all")

        # 3. Build restricted execution namespace
        namespace: dict[str, Any] = {
            "__builtins__": _SAFE_BUILTINS,
            "pd":           pd,
            "np":           np,
            "plt":          plt,
            "matplotlib":   matplotlib,
            "df":           df.copy(),  # always pass a copy so original is never mutated
        }

        # 4. Inject Plotly into namespace (optional — graceful if not installed)
        try:
            import plotly.express as px
            import plotly.graph_objects as go
            namespace["px"] = px
            namespace["go"] = go
        except ImportError:
            pass

        # 5. Capture stdout
        captured_stdout = io.StringIO()

        # 6. Execute
        try:
            namespace["__builtins__"]["print"] = lambda *a, **kw: captured_stdout.write(
                " ".join(str(x) for x in a) + "\n"
            )
            exec(code, namespace)  # noqa: S102 — intentional, sandboxed
        except Exception:
            return ExecutionResult(
                success=False,
                error=traceback.format_exc(limit=0),
                stdout=captured_stdout.getvalue(),
            )

        # 7. Extract and normalize `result`
        raw_result = namespace.get("result", None)
        raw_result, rtype = _finalize_result(raw_result)

        return ExecutionResult(
            success=True,
            result=raw_result,
            result_type=rtype,
            stdout=captured_stdout.getvalue(),
        )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _static_check(code: str) -> Optional[str]:
    """
    Parse the code with the `ast` module and walk the tree looking for
    blocked imports or dangerous function calls.

    Returns a violation description string, or None if the code looks safe.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"Syntax error: {e}"

    for node in ast.walk(tree):
        # import foo  /  import foo as bar
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in _BLOCKED_IMPORTS:
                    return f"Blocked import: `{alias.name}`"

        # from foo import bar
        if isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".")[0]
            if module in _BLOCKED_IMPORTS:
                return f"Blocked import: `from {node.module} import …`"

        # Call to a blocked function name
        if isinstance(node, ast.Call):
            func_name = _get_call_name(node)
            if func_name and func_name in _BLOCKED_CALLS:
                if func_name not in {"print"}:  # print is allowed (captured)
                    return f"Blocked function call: `{func_name}()`"

    return None


def _get_call_name(node: ast.Call) -> Optional[str]:
    """Return the simple name of a Call node's function, if determinable."""
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _classify_result(value: Any) -> str:
    """Map a Python value to one of our result-type labels."""
    if value is None:
        return "none"
    if isinstance(value, pd.DataFrame):
        return "dataframe"
    # Check Plotly Figure before matplotlib to avoid mis-classification
    try:
        import plotly.graph_objects as go
        if isinstance(value, go.Figure):
            return "plotly"
    except ImportError:
        pass
    if isinstance(value, Figure):
        return "figure"
    if isinstance(value, str):
        return "text"
    return "scalar"


def _finalize_result(raw: Any) -> tuple[Any, str]:
    """
    Normalize common LLM mistakes and classify the result.
      • result = ax   → figure
      • result = None + open figure → figure
    Plotly figures are returned as-is (no post-processing needed).
    """
    value = raw

    # LLM returned an Axes object instead of a Figure
    if isinstance(value, Axes):
        value = value.figure

    # LLM forgot to assign result but left a figure open
    if value is None:
        fnums = plt.get_fignums()
        if fnums:
            value = plt.figure(fnums[-1])

    rtype = _classify_result(value)

    # Post-process matplotlib figures only
    if rtype == "figure":
        _ensure_figure_labeled(value)

    return value, rtype


def _ensure_figure_labeled(fig: Figure) -> None:
    """
    Enforce basic labeling for every matplotlib chart returned by the LLM.
    """
    for ax in fig.axes:
        if not ax.get_title():
            ax.set_title("Chart")
        if not ax.get_xlabel():
            ax.set_xlabel("X")
        if not ax.get_ylabel():
            ax.set_ylabel("Y")

        # Annotate bar charts with their values
        for rect in ax.patches:
            if not isinstance(rect, Rectangle):
                continue
            w = rect.get_width()
            h = rect.get_height()
            if w == 0 and h == 0:
                continue
            try:
                if abs(h) >= abs(w):
                    val = h
                    x = rect.get_x() + w / 2
                    y = rect.get_y() + h
                    ha, va = "center", "bottom"
                else:
                    val = w
                    x = rect.get_x() + w
                    y = rect.get_y() + rect.get_height() / 2
                    ha, va = "left", "center"
                if not np.isfinite(val):
                    continue
                ax.text(x, y, f"{val:g}", ha=ha, va=va, fontsize=8, color="#e6edf3")
            except Exception:
                continue

    try:
        fig.tight_layout()
    except Exception:
        pass
