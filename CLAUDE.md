# Lumina — Project Context for Claude

## What This Project Is

**Lumina** is a Streamlit multi-page web app that lets users upload Excel/CSV files and interact with their data through four distinct views:

1. **Chat** — Ask natural-language questions; Google Gemini generates pandas/Plotly/matplotlib code, runs it in a sandboxed executor, and renders tables, metrics, or interactive charts.
2. **Insights** — Auto-generated data profile dashboard: KPI strip, missing value chart, numeric histograms, Pearson correlation heatmap, outlier detection, category distributions, and time series trends.
3. **Graph** — Entity relationship graph visualizer. Detects column relationships (Pearson r, Cramer's V, shared names across files) and persists them in SQLite for cross-session exploration.
4. **Predictions** — Optional LLM-powered trend forecasts and causal factor analysis (user-triggered only, never automatic).

---

## File Structure

```
app.py                   ← Thin shell: page config, CSS injection, sidebar, file upload
state_manager.py         ← Canonical session state keys + init helpers
insight_engine.py        ← DataProfile dataclass + profile_dataframe() (pure pandas)
graph_engine.py          ← Entity/relationship detection + SQLite persistence + Plotly graph
export_utils.py          ← Excel export (xlsxwriter) + Markdown transcript export
gemini_llm.py            ← Gemini API wrapper: code gen, retry, follow-ups, predictions/causes
code_executor.py         ← Sandboxed exec() with AST static analysis + result typing
excel_processor.py       ← Load Excel/CSV, dtype coercion, schema string builder
demo_data.py             ← Reproducible 120-row demo sales workbook (2 sheets)
ui_theme.py              ← Design system: color tokens, CSS_BLOCK, PLOTLY_LAYOUT, HTML helpers
list_models.py           ← Dev utility only (not part of app)
pages/
  1_Chat.py              ← Q&A pipeline with self-healing retry + follow-up suggestions
  2_Insights.py          ← Auto-profile dashboard (all Plotly, dark theme)
  3_Graph.py             ← Network graph page + relationship table + join key cards
  4_Predictions.py       ← LLM predictions + causes (cached per file)
tests/
  conftest.py            ← Shared fixtures (sample_df, small_df, numeric_df)
  test_code_executor.py  ← 20+ tests: result types, blocked imports, sandbox behavior
  test_excel_processor.py← Schema, coerce_dtypes, sample rows, CSV load
  test_insight_engine.py ← DataProfile shape, missing, outliers, correlation, time series
  test_graph_engine.py   ← Column classification, Cramer's V, SQLite idempotency, graph build
  test_gemini_llm.py     ← _prune_history, _extract_code_block, _format_history, retry msg
  test_export_utils.py   ← Markdown and xlsx export correctness
  test_demo_data.py      ← Demo workbook structure (unchanged)
Dockerfile               ← python:3.11-slim, EXCЕЛCHAT_DB_PATH env var, port 8501
.dockerignore
requirements.txt         ← All deps pinned
.env / .env.example      ← GEMINI_API_KEY + optional GEMINI_MODEL
```

---

## Q&A Pipeline (per user turn)

```
user question
    → gemini_llm.generate_code()        # schema + 5-row sample + pruned history → Gemini
    → gemini_llm.extract_code()         # pulls ```python block
    → code_executor.run(code, df)       # AST check → restricted exec() → typed result
    → [on failure] generate_retry() → run() again (up to 2 retries)
    → result typed: plotly | dataframe | figure | scalar | text | none
    → rendered in st.chat_message()
    → gemini_llm.generate_followups()   # separate low-temp call → 3 suggestion buttons
```

---

## Key Files In Detail

### `ui_theme.py`
Single source of truth for the design system. Every page imports from here.
- **Color tokens**: `BG_BASE=#0a0e17`, `BG_SURFACE=#111827`, `BG_RAISED=#1a2233`, `BORDER=#1e2d40`, `BORDER_LIT=#2a3f5a`, `ACCENT=#2dd4bf`, `ACCENT_DIM=#0d9488`, `TEXT_PRI=#f0f6fc`, `TEXT_SEC=#8d9db0`, `TEXT_DIM=#4a5568`, `AMBER=#ffa657`
- **`PLOTLY_LAYOUT`**: shared dict for all Plotly figures — `template="plotly_dark"`, DM Sans font, consistent margins, hover label styling. Merge with `fig.update_layout(**PLOTLY_LAYOUT)`. **Do NOT pass to `go.Layout()` directly** — use `fig.update_layout()` instead to avoid strict validation errors.
- **`CSS_BLOCK`**: f-string `<style>` block with `@keyframes fadeInUp/slideInUp/pulseBorder/dotPulse`, base layout, sidebar classes (`.sidebar-wordmark`, `.sidebar-section-label`), button styles, chat message styles, `.kpi-strip`, `.kpi-card`, `.chart-card`, `.graph-card`, `.graph-legend`, `.insight-card`, `.join-card`, `.corr-chip`, `.empty-state`, `.disclaimer`, `.followup-btn`, `.section-header`, `.page-subtitle`.
- **HTML helpers**: `kpi_card(value, label, warning=False)`, `section_header(title)`, `insight_card_html(...)`, `cause_card_html(...)`

### `app.py`
Thin shell — only page config, CSS, sidebar, and file loading.
- Calls `insight_engine.profile_dataframe()` and `graph_engine.register_file()` on every upload
- Session state managed through `state_manager.init_state()`
- Sidebar sections labeled `WORKSPACE` and `NAVIGATION` via `.sidebar-section-label` HTML
- No Q&A logic here — that lives in `pages/1_Chat.py`

### `state_manager.py`
- `_DEFAULTS` dict holds all session state keys with defaults
- `init_state()` — idempotent, called at top of every page
- `clear_data_state()` — resets all data-related keys on new file load
- `resolve_api_key()` — returns key from env or session state

### `gemini_llm.py`
Two `GenerativeModel` instances:
- `_code_model` (temp=0.1): code generation, retry, extract_code
- `_analysis_model` (temp=0.3): follow-ups (JSON array), predictions (markdown cards), causes (markdown cards)

Key methods:
- `generate_code(schema, sample, question, history)` — main code gen with history pruning
- `generate_retry(question, failed_code, error, schema, sample)` — self-healing retry
- `generate_followups(schema, question, answer_summary)` → `list[str]` (3 items)
- `generate_predictions(schema, summary)` → markdown string with `### Prediction N:` cards
- `generate_causes(schema, summary, top_corr)` → markdown string with `### Factor N:` cards
- `_prune_history(history, max_turns=10)` — sliding window before building Gemini history
- `extract_code(response)` — extracts ```python block, falls back to bare fences

### `code_executor.py`
- **Blocked imports** (AST): `os`, `sys`, `subprocess`, `shutil`, `socket`, `requests`, `urllib`, `importlib`, `builtins`, `eval`, `exec` — checked before any execution
- **Namespace**: `pd`, `np`, `plt`, `matplotlib`, `px` (plotly.express), `go` (plotly.graph_objects), `df` (copy of user DataFrame)
- **Result types**: `plotly | dataframe | figure | scalar | text | none`
- `_classify_result()` checks for `plotly.graph_objects.Figure` first, then matplotlib Figure, then DataFrame, then scalar
- `_ensure_figure_labeled()` adds fallback labels to matplotlib figures

### `insight_engine.py`
Pure pandas computation — zero Streamlit imports. Computes `DataProfile`:
- `missing_counts`, `missing_pct` (per column)
- `numeric_cols`, `describe_df` (df.describe() output)
- `corr_matrix` (Pearson, None if < 2 numeric cols), `top_corr_pairs` (top 5 by abs(r))
- `outlier_counts` (IQR × 1.5 method)
- `categorical_cols`, `value_counts` (top 20 per col)
- `date_cols`, `time_series` (monthly resampled, `"M"` not `"ME"` — pandas 2.1.4 compat)
- `statistical_summary` (compact text for LLM prompts)

### `graph_engine.py`
SQLite schema: `files`, `columns`, `relationships` tables in `excелchat.db`.

Column classification in `_classify_column()`:
- ID heuristic applies only to integer-typed columns (not float) — prevents continuous numeric mis-classification
- `entity` = low cardinality categorical or integer with ≤ 30 unique values
- `numeric` = numeric, not entity, not id
- `datetime` = datetime64 dtype
- `text` = high-cardinality string

Relationship detection:
- `correlation`: Pearson |r| > 0.3 between numeric pairs within a file
- `co_occurrence`: Cramer's V > 0.1 between categorical pairs within a file
- `shared_name`: same column name in different files (join key signal, strength=1.0)

`build_plotly_graph()` uses NetworkX `spring_layout(seed=42)`:
- Nodes: degree-scaled size (12–28px), colored by col_type, border matches node color
- Edges: strength-scaled width (0.8/1.5/2.5), opacity 0.35
- Labels: entity/ID nodes always visible; numeric/text nodes show label only on hover
- **Use `fig.update_layout(**PLOTLY_LAYOUT_overrides)` not `go.Layout(**PLOTLY_LAYOUT)` directly**

### `export_utils.py`
- `export_chat_markdown(history, file_name)` → Markdown transcript string
- `export_results_to_xlsx(history)` → bytes; one sheet per DataFrame result named `Result_N`

### `excel_processor.py`
- `load_excel()`: reads all sheets with `pd.read_excel(sheet_name=None)`, CSV handled separately
- `coerce_dtypes()`: whitespace-strip column names, `format="mixed"` for datetime inference (not deprecated `infer_datetime_format=True`)
- `build_schema_description()`: dtype, nulls, min/max/mean for numeric, sample uniques for categorical, date range for datetimes

---

## Design System

Typography: `Playfair Display 700` (hero titles only) · `DM Sans 400/500/600` (body/headings) · `DM Mono 400` (code/numbers)

Spacing: 4px base grid — xs=4, sm=8, md=16, lg=24, xl=40

Animations: `fadeInUp` (sections), `slideInUp` (buttons), `pulseBorder` (CTA idle), `dotPulse` (spinner)

No emojis anywhere in visible UI copy. No gradients in the sidebar. No exclamation marks in copy. Error messages are factual ("No data loaded" not "Oops!").

---

## Tech Stack

| Layer | Library / Version |
|-------|---------|
| UI | Streamlit 1.35.0 |
| LLM | `google-generativeai==0.5.4`, Gemini 2.0 Flash |
| Data | pandas 2.1.4, numpy 1.26.4 |
| Charts | Plotly 5.22.0 (primary), matplotlib 3.8.3 (fallback) |
| Graph | networkx 3.3 (spring_layout) |
| Stats | scipy 1.13.0 (Cramer's V via chi2_contingency) |
| Excel | openpyxl (xlsx read), xlrd (xls), xlsxwriter 3.2.0 (export) |
| DB | SQLite (stdlib) — `excелchat.db` for graph cross-session |
| Config | python-dotenv |
| Tests | pytest + pytest-cov + pytest-mock |

---

## Security Model

- **In-process sandbox** — NOT a container/seccomp jail; suitable for trusted/demo use
- Blocked imports checked via `ast.parse()` before `exec()`
- Restricted `__builtins__` dict (explicit allowlist ~40 names) passed to `exec()`
- DataFrame is `.copy()`-ed — original never mutated
- User-supplied code never executed — only Gemini-generated code through the controlled prompt

---

## Test Coverage (98 tests, all passing)

| File | What's tested |
|------|--------------|
| `test_code_executor.py` | scalar/text/dataframe/plotly/figure results, axes normalization, blocked imports, syntax error, stdout capture |
| `test_excel_processor.py` | schema string, coerce_dtypes, sample rows, CSV load |
| `test_insight_engine.py` | DataProfile shape, missing counts/pct, IQR outliers, correlation matrix, top pairs, value_counts, time series |
| `test_graph_engine.py` | column classification, Cramer's V, register_file idempotency, shared_name detection, build_plotly_graph |
| `test_gemini_llm.py` | _prune_history, _extract_code_block, _format_history, _build_retry_message |
| `test_export_utils.py` | markdown transcript, xlsx sheet count + content |
| `test_demo_data.py` | demo workbook shape and columns |

Run: `pytest tests/ --cov=. --cov-report=term-missing --cov-omit="tests/*,pages/*,app.py,.venv/*"`

---

## Running the App

```bash
pip install -r requirements.txt
cp .env.example .env          # add GEMINI_API_KEY=your_key_here
streamlit run app.py
```

Docker:
```bash
docker build -t excелchat .
docker run -p 8501:8501 -e GEMINI_API_KEY=xxx excелchat
```

---

## Known Limitations

- Gemini API calls are synchronous — no streaming; UI shows a spinner during generation
- History pruning is sliding window only (last 10 turns) — no summarization
- Sandbox is in-process — sufficient for demo; not for untrusted multi-user deployment
- `excелchat.db` path defaults to the working directory — set `EXCЕЛCHAT_DB_PATH` env var in production
- Plotly `PLOTLY_LAYOUT` must be applied via `fig.update_layout()`, not `go.Layout(**PLOTLY_LAYOUT)` (strict validator rejects some fields)
