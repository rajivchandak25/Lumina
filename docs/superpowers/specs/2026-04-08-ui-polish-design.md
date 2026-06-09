# ExcelChat UI Polish — Design Spec
**Date:** 2026-04-08
**Approach:** Option B — CSS overhaul + unified Plotly theme system

---

## Goal

Elevate the UI to a professional data-tool aesthetic (Retool/Metabase reference). Charts, diagrams, and the graph visualizer should feel premium. Moderate animations: fade-ins, skeleton loaders, entrance effects. No emojis or informal copy anywhere in the project.

---

## 1. Design System (`ui_theme.py`)

Single module exporting color tokens, a CSS string, and a Plotly layout dict. Every page imports it.

### Color tokens
```python
BG_BASE    = "#0a0e17"
BG_SURFACE = "#111827"
BG_RAISED  = "#1a2233"
BORDER     = "#1e2d40"
BORDER_LIT = "#2a3f5a"
ACCENT     = "#2dd4bf"
ACCENT_DIM = "#0d9488"
TEXT_PRI   = "#f0f6fc"
TEXT_SEC   = "#8d9db0"
TEXT_DIM   = "#4a5568"
```

### Typography
- Display: `Playfair Display` 700, 2rem — page hero titles only
- Heading: `DM Sans` 600, 1.1rem — section labels
- Body: `DM Sans` 400, 0.92rem
- Mono: `DM Mono` 400, 0.82rem — code, schema, numbers

### Spacing (4px base grid)
`xs=4px, sm=8px, md=16px, lg=24px, xl=40px`

### Elevation
- `shadow-sm`: `0 1px 3px rgba(0,0,0,0.4)`
- `shadow-md`: `0 4px 12px rgba(0,0,0,0.5), 0 1px 3px rgba(0,0,0,0.3)`
- `shadow-glow`: `0 0 20px rgba(45,212,191,0.12)`

### Plotly dark template (`PLOTLY_LAYOUT`)
Consistent across all pages:
```python
PLOTLY_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor=BG_BASE,
    plot_bgcolor=BG_SURFACE,
    font=dict(family="DM Sans, sans-serif", color=TEXT_SEC, size=12),
    title_font=dict(family="DM Sans, sans-serif", color=TEXT_PRI, size=14),
    margin=dict(l=16, r=16, t=40, b=16),
    hoverlabel=dict(bgcolor=BG_RAISED, bordercolor=BORDER_LIT, font_size=12),
    coloraxis_colorbar=dict(tickfont=dict(color=TEXT_SEC)),
    xaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER),
    yaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER),
)
```

### CSS keyframe animations
```css
@keyframes fadeInUp   { from { opacity:0; transform:translateY(8px) } to { opacity:1; transform:translateY(0) } }
@keyframes slideInUp  { from { opacity:0; transform:translateY(12px)} to { opacity:1; transform:translateY(0) } }
@keyframes countUp    { from { opacity:0 } to { opacity:1 } }
@keyframes pulse-border { 0%,100% { box-shadow: 0 0 0 0 rgba(45,212,191,0.3) } 50% { box-shadow: 0 0 0 4px rgba(45,212,191,0) } }
@keyframes shimmer    { from { background-position: -200% 0 } to { background-position: 200% 0 } }
```

---

## 2. Sidebar

- Background: `BG_SURFACE`, right border `1px solid BORDER`
- Wordmark `ExcelChat`: `DM Sans` 500, 1rem, `TEXT_SEC` — small and refined
- Section labels (`WORKSPACE`, `NAVIGATION`): uppercase, 0.65rem, letter-spacing 0.1em, `TEXT_DIM`
- File uploader: `BG_RAISED` background, `1px dashed BORDER_LIT` border, `border-radius: 8px`
- All buttons: ghost style — transparent bg, `1px solid BORDER`, `TEXT_SEC`, hover: `3px solid ACCENT` left border, `BG_RAISED` bg
- No gradients anywhere in the sidebar
- Metric cards (Rows/Columns): side-by-side `BG_RAISED` cards, `border-radius: 6px`
- Dividers: `1px solid BORDER`, `8px` vertical margin
- Hover animation: `0.15s ease` left-border slide

---

## 3. Chat Page

- User message: `BG_SURFACE` bg, `shadow-sm`, `3px solid ACCENT_DIM` left border
- Assistant message: `BG_SURFACE` bg, `shadow-sm`, no colored border
- Code expander: `BG_RAISED` bg, `DM Mono`, keyword coloring via CSS
- Charts: rendered inside `BG_SURFACE` card, `border-radius: 10px`, `shadow-md`
- Follow-up buttons: pill-shaped (`border-radius: 999px`), `BG_RAISED` bg, `1px solid BORDER_LIT`, 0.8rem — subtle secondary
- Download buttons: text links, right-aligned, `TEXT_SEC` — subordinate to answer
- Spinner: 3-dot CSS pulse animation replacing native Streamlit spinner
- New message animation: `slideInUp` 0.2s, `animation-delay: 0.05s` per follow-up button

---

## 4. Insights Page

**KPI strip:** 5 custom HTML cards (replacing `st.metric`):
- `BG_SURFACE` bg, `1px solid BORDER`, `border-radius: 10px`, `shadow-sm`
- Number: `DM Mono` 1.6rem `TEXT_PRI`; label: 0.7rem uppercase `TEXT_DIM`
- Missing cells card: `3px solid ACCENT` left border if > 0
- Animation: `countUp` 0.6s on page load

**Section headers:** `border-bottom: 1px solid BORDER`, `16px` padding-bottom

**Histogram grid:** 3-column CSS grid, `gap: 16px`, each chart in `BG_SURFACE` card, height `200px`, `border-radius: 10px`, `shadow-sm`

**Correlation panel:** Full-width heatmap. Top pairs as horizontal chips — `BG_RAISED` pill, colored `r` value badge (teal=positive, amber=negative)

**All chart cards:** `transition: box-shadow 0.2s` on hover → `shadow-glow`

**Animations:** `fadeInUp` with staggered `animation-delay: 0.1s` per section

---

## 5. Graph Page

**Graph container:** Full-width `BG_SURFACE` card, `border-radius: 12px`, `shadow-md`, height `650px`. Chart bleeds edge-to-edge inside card.

**Plotly graph upgrades (in `graph_engine.py`):**
- Node size: scaled by degree, min 12px, max 28px
- Node border: `2px solid` at 60% opacity of node color
- Edge width: weak=0.8px, medium=1.5px, strong=2.5px (by strength)
- Edge opacity: 0.35 default
- Labels: entity/ID nodes always visible; numeric/text nodes label on hover only
- Background: `BG_BASE`

**Controls row:** Styled toggle pill for "Current File / All Sessions". Filter chips for relationship types — `BG_RAISED` inactive, `ACCENT_DIM` active.

**Legend:** Horizontal colored dot row inside graph card header — not below chart.

**Relationship table:** Alternating row bg, monospace Strength column, relationship type as colored badge pill.

**Join key cards:** `BG_SURFACE` card, `3px solid ACCENT` left border, source/target file + column name + "Potential join key" badge.

**Animations:**
- Graph card: `fadeInUp` 0.3s
- Filter chip: `0.15s ease` bg transition
- Card hover: `shadow-glow` `0.25s ease`

---

## 6. Predictions Page

**Empty state:** `1px dashed BORDER_LIT` rect, `border-radius: 12px`, `padding: 40px`, `◈` character in `ACCENT`, ghost generate button with pulse-border animation.

**Insight cards:** Each `### Prediction N:` / `### Factor N:` block parsed into a card:
- `BG_SURFACE` bg, `1px solid BORDER`, `border-radius: 10px`, `shadow-sm`
- Title: `DM Sans` 600 `TEXT_PRI`; confidence badge: teal=High, amber=Medium, muted=Low
- Field labels: `TEXT_DIM` uppercase 0.65rem; content: `TEXT_SEC` 0.88rem
- Predictions: `3px solid ACCENT` left border; Causes: `3px solid #ffa657` left border

**Tabs:** Two pill buttons — `BG_RAISED` inactive, `ACCENT_DIM` active. No Streamlit native tabs.

**Disclaimer:** `TEXT_DIM` 0.75rem, `border-top: 1px solid BORDER`, not `st.caption`.

**Animations:** Cards stagger in with `fadeInUp` + 0.1s delay per card. Generate button idle: `pulse-border`.

---

## 7. Copy / Tone

Remove all emoji from every file. Replace informal labels:
- "Try sample dataset" → "Load sample data"
- "Clear chat" → "Clear conversation"
- Page names: `Chat`, `Insights`, `Graph`, `Predictions` (no emoji prefixes in filenames where possible, but Streamlit requires them for ordering — strip from display labels via CSS)
- No exclamation marks in UI copy
- Error messages: factual, not apologetic ("No data loaded" not "Oops, no file yet!")

---

## Files to Modify

| File | Change |
|---|---|
| `ui_theme.py` | NEW — design tokens, CSS string, Plotly layout dict |
| `app.py` | Replace CSS block, import `ui_theme`, remove emojis |
| `pages/1_Chat.py` (rename to `pages/1_Chat.py`) | Restyle messages, buttons, spinner |
| `pages/2_Insights.py` | KPI cards, chart grid, correlation panel |
| `pages/3_Graph.py` | Controls row, legend, table, join key cards |
| `pages/4_Predictions.py` | Tab pills, insight card parser, empty states |
| `graph_engine.py` | Node/edge sizing, label visibility, `PLOTLY_LAYOUT` usage |

---

## Non-Goals

- No layout restructuring (column counts stay the same)
- No new features
- No changes to backend logic (insight_engine, code_executor, etc.)
- No JS injection
