"""
graph_engine.py
───────────────
Entity relationship graph engine for Lumina.

Responsibilities:
  • Classify columns into types: entity, numeric, datetime, text
  • Detect relationships between columns within a file and across files
  • Persist schemas + relationships to SQLite (cross-session memory)
  • Build a Plotly interactive network graph for rendering

Relationship types detected:
  1. correlation   — Pearson r between numeric columns (|r| > 0.3)
  2. co_occurrence — Cramer's V between categorical columns (V > 0.1)
  3. shared_name   — Same column name appearing in DIFFERENT files (join key candidate)

SQLite schema (lumina.db):
  files(id, file_name, sheet_name, registered_at, row_count, col_count)
  columns(id, file_id, col_name, col_type, dtype, n_unique, is_entity, is_id_col)
  relationships(id, col_a_id, col_b_id, relationship, strength, created_at)
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Optional

import networkx as nx
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from ui_theme import PLOTLY_LAYOUT, BG_BASE, BG_SURFACE

# ── Database path ─────────────────────────────────────────────────────────────
_DEFAULT_DB = os.getenv("LUMINA_DB_PATH", "lumina.db")


# ── Data containers ───────────────────────────────────────────────────────────

@dataclass
class GraphMeta:
    nodes: list[dict]   # {id, label, file, sheet, col_type, is_entity, is_id}
    edges: list[dict]   # {source, target, rel, weight, label}
    file_name:  str
    sheet_name: str


# ── Public API ────────────────────────────────────────────────────────────────

def register_file(
    file_name: str,
    df: pd.DataFrame,
    sheet_name: str = "Sheet1",
    db_path: str = _DEFAULT_DB,
) -> GraphMeta:
    """
    Persist the schema of *df* to SQLite and detect all relationships.

    Safe to call multiple times for the same file — uses UPSERT logic
    (DELETE + re-INSERT) so relationships are always fresh.

    Returns a GraphMeta for the current file (not cross-session).
    """
    _ensure_schema(db_path)

    with _db(db_path) as conn:
        # UPSERT: remove existing entry for this file+sheet, then re-insert
        cur = conn.execute(
            "SELECT id FROM files WHERE file_name=? AND sheet_name=?",
            (file_name, sheet_name),
        )
        row = cur.fetchone()
        if row:
            file_id = row[0]
            conn.execute("DELETE FROM columns WHERE file_id=?", (file_id,))
            conn.execute("DELETE FROM files WHERE id=?", (file_id,))
            conn.execute(
                "DELETE FROM relationships WHERE col_a_id NOT IN (SELECT id FROM columns)"
            )

        # Insert file record
        cur = conn.execute(
            "INSERT INTO files (file_name, sheet_name, row_count, col_count) VALUES (?,?,?,?)",
            (file_name, sheet_name, len(df), df.shape[1]),
        )
        file_id = cur.lastrowid

        # Insert column records
        col_id_map: dict[str, int] = {}
        for col in df.columns:
            col_type, is_entity, is_id = _classify_column(col, df[col])
            n_unique = int(df[col].nunique())
            dtype_str = str(df[col].dtype)
            cur = conn.execute(
                "INSERT INTO columns (file_id, col_name, col_type, dtype, n_unique, is_entity, is_id_col) "
                "VALUES (?,?,?,?,?,?,?)",
                (file_id, str(col), col_type, dtype_str, n_unique, int(is_entity), int(is_id)),
            )
            col_id_map[str(col)] = cur.lastrowid

        # Detect within-file relationships
        rels = _detect_within_file_relationships(df, col_id_map)

        # Detect cross-file shared_name relationships
        rels += _detect_shared_name_relationships(conn, file_id, col_id_map)

        # Insert relationships
        for (col_a_id, col_b_id, rel, strength) in rels:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO relationships "
                    "(col_a_id, col_b_id, relationship, strength) VALUES (?,?,?,?)",
                    (col_a_id, col_b_id, rel, strength),
                )
            except Exception:
                pass

        conn.commit()

    return _build_meta_for_file(file_name, sheet_name, df, col_id_map, db_path)


def load_full_graph(db_path: str = _DEFAULT_DB) -> GraphMeta:
    """
    Load ALL nodes and edges from SQLite for the cross-session graph view.
    Used by pages/3_Graph.py to show the complete cross-dataset picture.
    """
    _ensure_schema(db_path)

    nodes: list[dict] = []
    edges: list[dict] = []

    with _db(db_path) as conn:
        # Load all columns as nodes
        cur = conn.execute(
            "SELECT c.id, c.col_name, c.col_type, c.is_entity, c.is_id_col, "
            "       f.file_name, f.sheet_name "
            "FROM columns c JOIN files f ON c.file_id = f.id"
        )
        node_by_id: dict[int, dict] = {}
        for row in cur.fetchall():
            cid, col_name, col_type, is_entity, is_id, file_name, sheet_name = row
            node = {
                "id":       f"{file_name}::{sheet_name}::{col_name}",
                "label":    col_name,
                "file":     file_name,
                "sheet":    sheet_name,
                "col_type": col_type,
                "is_entity": bool(is_entity),
                "is_id":    bool(is_id),
            }
            nodes.append(node)
            node_by_id[cid] = node

        # Load all relationships as edges
        cur = conn.execute(
            "SELECT r.col_a_id, r.col_b_id, r.relationship, r.strength "
            "FROM relationships r"
        )
        for row in cur.fetchall():
            a_id, b_id, rel, strength = row
            if a_id in node_by_id and b_id in node_by_id:
                node_a = node_by_id[a_id]
                node_b = node_by_id[b_id]
                edges.append({
                    "source": node_a["id"],
                    "target": node_b["id"],
                    "rel":    rel,
                    "weight": float(strength or 0),
                    "label":  f"{rel}: {float(strength or 0):.2f}",
                })

    return GraphMeta(
        nodes=nodes,
        edges=edges,
        file_name="(all sessions)",
        sheet_name="",
    )


def build_plotly_graph(meta: GraphMeta) -> go.Figure:
    """
    Build an interactive Plotly network graph from a GraphMeta.

    Nodes are colored by column type:
      entity   → teal   (#58d9c8)
      numeric  → blue   (#79c0ff)
      datetime → orange (#ffa657)
      text     → grey   (#8b949e)

    Edge width and opacity are proportional to relationship strength.
    Layout uses networkx spring_layout for readable positioning.
    """
    if not meta.nodes:
        fig = go.Figure()
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor=BG_BASE,
            annotations=[dict(text="No nodes to display", showarrow=False,
                              font=dict(size=16, color="#8b949e"))],
        )
        return fig

    # Build networkx graph for layout computation
    G = nx.Graph()
    for node in meta.nodes:
        G.add_node(node["id"], **node)
    for edge in meta.edges:
        G.add_edge(edge["source"], edge["target"],
                   weight=edge["weight"], rel=edge["rel"])

    # Spring layout — deterministic, readable for 5–200 nodes
    k_val = 3.0 / max(1, len(meta.nodes) ** 0.5)
    pos = nx.spring_layout(G, seed=42, k=k_val, iterations=50)

    _COLOR_MAP = {
        "entity":   "#58d9c8",
        "numeric":  "#79c0ff",
        "datetime": "#ffa657",
        "text":     "#8b949e",
    }

    # ── Edge traces (one per relationship type for legend grouping) ───────────
    _REL_COLORS = {
        "correlation":   "#79c0ff",
        "co_occurrence": "#58d9c8",
        "shared_name":   "#ffa657",
    }

    rel_groups: dict[str, list[dict]] = {}
    for edge in meta.edges:
        rel_groups.setdefault(edge["rel"], []).append(edge)

    edge_traces: list[go.Scatter] = []
    for rel_type, rel_edges in rel_groups.items():
        edge_x, edge_y = [], []
        for edge in rel_edges:
            src = edge["source"]
            tgt = edge["target"]
            if src not in pos or tgt not in pos:
                continue
            x0, y0 = pos[src]
            x1, y1 = pos[tgt]
            edge_x += [x0, x1, None]
            edge_y += [y0, y1, None]

        avg_weight = sum(e["weight"] for e in rel_edges) / max(len(rel_edges), 1)
        if avg_weight < 0.3:
            edge_width = 0.8
        elif avg_weight < 0.7:
            edge_width = 1.5
        else:
            edge_width = 2.5

        edge_traces.append(go.Scatter(
            x=edge_x, y=edge_y,
            mode="lines",
            name=rel_type.replace("_", " ").title(),
            line=dict(width=edge_width, color=_REL_COLORS.get(rel_type, "#484f58")),
            opacity=0.35,
            hoverinfo="none",
        ))

    # ── Node trace ────────────────────────────────────────────────────────────
    node_x, node_y = [], []
    node_colors, node_labels, node_hovers = [], [], []
    node_sizes = []

    for node in meta.nodes:
        nid = node["id"]
        if nid not in pos:
            continue
        x, y = pos[nid]
        node_x.append(x)
        node_y.append(y)
        node_colors.append(_COLOR_MAP.get(node["col_type"], "#484f58"))

        label = node["label"]
        degree = G.degree(nid) if nid in G else 0
        # Scale: min 12, max 28, based on degree
        size = max(12, min(28, 12 + degree * 3))
        node_sizes.append(size)

        is_entity_or_id = node.get("is_entity") or node.get("is_id")
        display_label = label if is_entity_or_id else ""
        node_labels.append(display_label)
        hover = (
            f"<b>{label}</b><br>"
            f"File: {node.get('file', '')}<br>"
            f"Sheet: {node.get('sheet', '')}<br>"
            f"Type: {node.get('col_type', '')}<br>"
            f"Connections: {degree}"
        )
        node_hovers.append(hover)

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode="markers+text",
        name="Columns",
        text=node_labels,
        textposition="top center",
        textfont=dict(size=10, color="#e6edf3"),
        marker=dict(
            color=node_colors,
            size=node_sizes,
            line=dict(width=2, color=node_colors),  # border matches node color at reduced opacity via marker opacity
            opacity=0.9,
        ),
        hovertext=node_hovers,
        hoverinfo="text",
    )

    # ── Legend for node types ─────────────────────────────────────────────────
    legend_traces = [
        go.Scatter(x=[None], y=[None], mode="markers", name=label,
                   marker=dict(color=color, size=10))
        for label, color in [
            ("Entity column",   "#58d9c8"),
            ("Numeric column",  "#79c0ff"),
            ("DateTime column", "#ffa657"),
            ("Text column",     "#8b949e"),
        ]
    ]

    layout_kwargs = dict(PLOTLY_LAYOUT)
    layout_kwargs.update(dict(
        title=dict(
            text=f"Entity Relationship Graph — {meta.file_name}",
            font=dict(size=16, color="#e6edf3", family="DM Sans, sans-serif"),
        ),
        showlegend=True,
        legend=dict(bgcolor=BG_SURFACE, bordercolor="#1e2d40", borderwidth=1, font=dict(color="#f0f6fc", size=11)),
        hovermode="closest",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        margin=dict(l=20, r=20, t=60, b=20),
        height=650,
    ))

    fig = go.Figure(data=edge_traces + [node_trace] + legend_traces)
    fig.update_layout(**layout_kwargs)

    return fig


def get_all_files(db_path: str = _DEFAULT_DB) -> list[dict]:
    """Return a list of registered file records (for display in sidebar/graph page)."""
    _ensure_schema(db_path)
    with _db(db_path) as conn:
        cur = conn.execute(
            "SELECT file_name, sheet_name, registered_at, row_count, col_count "
            "FROM files ORDER BY registered_at DESC"
        )
        return [
            {"file": r[0], "sheet": r[1], "at": r[2], "rows": r[3], "cols": r[4]}
            for r in cur.fetchall()
        ]


# ── Column classification ─────────────────────────────────────────────────────

def _classify_column(col: str, series: pd.Series) -> tuple[str, bool, bool]:
    """
    Returns (col_type, is_entity, is_id_col).

    col_type: 'entity' | 'numeric' | 'datetime' | 'text'
    is_entity: True if the column represents a discrete categorical dimension
    is_id_col: True if the column looks like a primary/foreign key
    """
    col_lower = str(col).lower().strip()
    n_total   = len(series.dropna())
    n_unique  = series.nunique()
    cardinality_ratio = n_unique / max(n_total, 1)

    # ID detection: exact 'id', ends with _id/_key/_code, or near-perfect unique INTEGER
    is_id = (
        col_lower in ("id",) or
        any(col_lower.endswith(sfx) for sfx in ("_id", "_key", "_code", "_num")) or
        (cardinality_ratio > 0.95 and n_unique > 10 and pd.api.types.is_integer_dtype(series))
    )

    # Datetime
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime", False, False

    # Numeric
    if pd.api.types.is_numeric_dtype(series):
        if is_id:
            return "numeric", True, True
        if n_unique <= 30:
            return "entity", True, False
        return "numeric", False, False

    # String / object
    if cardinality_ratio < 0.5 or n_unique < 50:
        return "entity", True, bool(is_id)

    return "text", False, False


# ── Relationship detection ────────────────────────────────────────────────────

def _detect_within_file_relationships(
    df: pd.DataFrame,
    col_id_map: dict[str, int],
) -> list[tuple[int, int, str, float]]:
    """Detect correlation and co_occurrence relationships within a single file."""
    results: list[tuple[int, int, str, float]] = []
    cols = list(col_id_map.keys())

    # Numeric-numeric: Pearson correlation
    numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
    if len(numeric_cols) >= 2:
        try:
            corr = df[numeric_cols].corr()
            for i, ca in enumerate(numeric_cols):
                for cb in numeric_cols[i + 1:]:
                    r = float(corr.loc[ca, cb])
                    if pd.notna(r) and abs(r) > 0.3:
                        results.append((col_id_map[ca], col_id_map[cb], "correlation", round(r, 4)))
        except Exception:
            pass

    # Categorical-categorical: Cramer's V
    cat_cols = [
        c for c in cols
        if not pd.api.types.is_numeric_dtype(df[c])
        and not pd.api.types.is_datetime64_any_dtype(df[c])
        and df[c].nunique() < 50
    ]
    if len(cat_cols) >= 2:
        for i, ca in enumerate(cat_cols):
            for cb in cat_cols[i + 1:]:
                try:
                    # Keep row alignment intact; _cramers_v handles NaN filtering.
                    v = _cramers_v(df[ca], df[cb])
                    if v > 0.1:
                        results.append((col_id_map[ca], col_id_map[cb], "co_occurrence", round(v, 4)))
                except Exception:
                    pass

    return results


def _detect_shared_name_relationships(
    conn: sqlite3.Connection,
    current_file_id: int,
    col_id_map: dict[str, int],
) -> list[tuple[int, int, str, float]]:
    """
    Find columns in OTHER files that share the same name as columns in the current file.
    These are potential join keys (cross-dataset relationships).
    """
    results: list[tuple[int, int, str, float]] = []
    col_names = list(col_id_map.keys())
    if not col_names:
        return results

    placeholders = ",".join("?" for _ in col_names)
    try:
        cur = conn.execute(
            f"SELECT id, col_name FROM columns "
            f"WHERE col_name IN ({placeholders}) AND file_id != ?",
            col_names + [current_file_id],
        )
        for other_id, other_col_name in cur.fetchall():
            if other_col_name in col_id_map:
                current_col_id = col_id_map[other_col_name]
                results.append((current_col_id, other_id, "shared_name", 1.0))
    except Exception:
        pass

    return results


def _cramers_v(col_a: pd.Series, col_b: pd.Series) -> float:
    """Cramer's V association statistic between two categorical columns."""
    from scipy.stats import chi2_contingency

    # Align on common index
    combined = pd.concat([col_a, col_b], axis=1).dropna()
    if len(combined) < 5:
        return 0.0

    contingency = pd.crosstab(
        combined.iloc[:, 0].astype(str),
        combined.iloc[:, 1].astype(str),
    )
    if contingency.shape[0] < 2 or contingency.shape[1] < 2:
        return 0.0

    chi2, _, _, _ = chi2_contingency(contingency, correction=False)
    n = contingency.sum().sum()
    r, k = contingency.shape
    denom = n * (min(r, k) - 1)
    if denom == 0:
        return 0.0
    v = float(np.sqrt(chi2 / denom))
    return float(np.clip(v, 0.0, 1.0))


# ── SQLite helpers ────────────────────────────────────────────────────────────

@contextmanager
def _db(path: str):
    conn = sqlite3.connect(path, timeout=10)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def _ensure_schema(db_path: str) -> None:
    """Create SQLite tables if they don't exist yet."""
    with _db(db_path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS files (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name     TEXT NOT NULL,
                sheet_name    TEXT NOT NULL DEFAULT 'Sheet1',
                registered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                row_count     INTEGER,
                col_count     INTEGER
            );

            CREATE TABLE IF NOT EXISTS columns (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id    INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
                col_name   TEXT NOT NULL,
                col_type   TEXT NOT NULL,
                dtype      TEXT,
                n_unique   INTEGER,
                is_entity  INTEGER DEFAULT 0,
                is_id_col  INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS relationships (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                col_a_id     INTEGER NOT NULL REFERENCES columns(id) ON DELETE CASCADE,
                col_b_id     INTEGER NOT NULL REFERENCES columns(id) ON DELETE CASCADE,
                relationship TEXT NOT NULL,
                strength     REAL,
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(col_a_id, col_b_id, relationship)
            );

            CREATE INDEX IF NOT EXISTS idx_columns_col_name ON columns(col_name);
            CREATE INDEX IF NOT EXISTS idx_columns_file_id  ON columns(file_id);
        """)
        conn.commit()


# ── Internal helper for building GraphMeta from freshly inserted data ─────────

def _build_meta_for_file(
    file_name: str,
    sheet_name: str,
    df: pd.DataFrame,
    col_id_map: dict[str, int],
    db_path: str,
) -> GraphMeta:
    """Build a GraphMeta for the just-registered file by querying the DB."""
    nodes: list[dict] = []
    edges: list[dict] = []

    with _db(db_path) as conn:
        # Get this file's id
        cur = conn.execute(
            "SELECT id FROM files WHERE file_name=? AND sheet_name=?",
            (file_name, sheet_name),
        )
        row = cur.fetchone()
        if not row:
            return GraphMeta(nodes=[], edges=[], file_name=file_name, sheet_name=sheet_name)
        file_id = row[0]

        # Nodes
        cur = conn.execute(
            "SELECT id, col_name, col_type, is_entity, is_id_col FROM columns WHERE file_id=?",
            (file_id,),
        )
        node_by_id: dict[int, dict] = {}
        for cid, col_name, col_type, is_entity, is_id in cur.fetchall():
            node = {
                "id":       f"{file_name}::{sheet_name}::{col_name}",
                "label":    col_name,
                "file":     file_name,
                "sheet":    sheet_name,
                "col_type": col_type,
                "is_entity": bool(is_entity),
                "is_id":    bool(is_id),
            }
            nodes.append(node)
            node_by_id[cid] = node

        # Edges involving this file's columns
        col_ids = list(node_by_id.keys())
        if col_ids:
            placeholders = ",".join("?" for _ in col_ids)
            cur = conn.execute(
                f"SELECT col_a_id, col_b_id, relationship, strength FROM relationships "
                f"WHERE col_a_id IN ({placeholders}) OR col_b_id IN ({placeholders})",
                col_ids + col_ids,
            )
            for a_id, b_id, rel, strength in cur.fetchall():
                for cid in (a_id, b_id):
                    if cid in node_by_id:
                        continue
                    ext_cur = conn.execute(
                        "SELECT c.id, c.col_name, c.col_type, c.is_entity, c.is_id_col, "
                        "       f.file_name, f.sheet_name "
                        "FROM columns c JOIN files f ON c.file_id = f.id "
                        "WHERE c.id=?",
                        (cid,),
                    )
                    ext = ext_cur.fetchone()
                    if not ext:
                        continue
                    ecid, col_name, col_type, is_entity, is_id, ext_file, ext_sheet = ext
                    ext_node = {
                        "id":       f"{ext_file}::{ext_sheet}::{col_name}",
                        "label":    col_name,
                        "file":     ext_file,
                        "sheet":    ext_sheet,
                        "col_type": col_type,
                        "is_entity": bool(is_entity),
                        "is_id":    bool(is_id),
                    }
                    node_by_id[ecid] = ext_node
                    nodes.append(ext_node)

                if a_id in node_by_id and b_id in node_by_id:
                    node_a = node_by_id[a_id]
                    node_b = node_by_id[b_id]
                    edges.append({
                        "source": node_a["id"],
                        "target": node_b["id"],
                        "rel":    rel,
                        "weight": float(strength or 0),
                        "label":  f"{rel}: {float(strength or 0):.2f}",
                    })

    return GraphMeta(nodes=nodes, edges=edges, file_name=file_name, sheet_name=sheet_name)
