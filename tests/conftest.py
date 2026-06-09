"""
tests/conftest.py
─────────────────
Shared pytest fixtures for Lumina test suite.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Ensure project root is on sys.path so all modules are importable
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ── Data fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def sample_df() -> pd.DataFrame:
    """120-row sales DataFrame matching demo_data shape."""
    rng = np.random.default_rng(0)
    n = 120
    df = pd.DataFrame({
        "order_id":   range(1000, 1000 + n),
        "date":       pd.date_range("2024-01-01", periods=n, freq="D"),
        "region":     pd.array(rng.choice(["North", "South", "East", "West"], n)),
        "product":    pd.array(rng.choice(["Widget A", "Widget B", "Gadget"], n)),
        "quantity":   rng.integers(1, 25, n),
        "unit_price": np.round(rng.uniform(9.99, 199.99, n), 2),
        "revenue":    np.round(rng.uniform(50.0, 5000.0, n), 2),
    })
    return df


@pytest.fixture
def small_df() -> pd.DataFrame:
    """4-row DataFrame: 'a' has an IQR outlier (100), 'cat' is categorical."""
    return pd.DataFrame({
        "a":   [1, 2, 3, 100],
        "b":   [4, 5, 6, 7],
        "cat": ["x", "y", "x", "z"],
    })


@pytest.fixture
def numeric_df() -> pd.DataFrame:
    """Simple 2-column numeric DataFrame with known perfect correlation."""
    x = np.arange(10, dtype=float)
    return pd.DataFrame({"x": x, "y": x * 2.0})
