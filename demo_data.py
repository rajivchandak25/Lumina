"""
demo_data.py
────────────
Reproducible sample workbook for trying Lumina without uploading a file.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def get_demo_workbook() -> dict[str, pd.DataFrame]:
    """
    Return sheet name → DataFrame for a small, realistic sales-style dataset.
    """
    rng = np.random.default_rng(42)
    regions = ["North", "South", "East", "West"]
    products = ["Widget A", "Widget B", "Gadget", "Service"]

    n = 120
    df = pd.DataFrame(
        {
            "order_id": range(1000, 1000 + n),
            "date": pd.date_range("2024-01-01", periods=n, freq="D"),
            "region": rng.choice(regions, size=n),
            "product": rng.choice(products, size=n),
            "quantity": rng.integers(1, 25, size=n),
            "unit_price": np.round(rng.uniform(9.99, 199.99, size=n), 2),
        }
    )
    df["revenue"] = np.round(df["quantity"] * df["unit_price"], 2)

    # Second sheet: monthly rollup (for multi-sheet demos)
    monthly = (
        df.assign(month=df["date"].dt.to_period("M").astype(str))
        .groupby(["month", "region"], as_index=False)["revenue"]
        .sum()
        .sort_values(["month", "region"])
        .reset_index(drop=True)
    )

    return {
        "Orders": df,
        "Monthly by region": monthly,
    }
