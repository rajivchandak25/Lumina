# Lumina

Chat with your spreadsheets in plain English. Upload Excel or CSV, ask questions, and get **tables**, **metrics**, and **interactive charts** — powered by **Google Gemini** with **sandboxed Python** execution.

## Quick start

1. **Python 3.10+** recommended.

2. Create a virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and set your API key:

   ```env
   GEMINI_API_KEY=your_key_here
   ```

   Create a key at [Google AI Studio](https://aistudio.google.com/app/apikey).

4. Run the app:

   ```bash
   streamlit run app.py
   ```

5. Open the URL shown in the terminal (usually `http://localhost:8501`).

## Features

- **Multi-sheet Excel** and **CSV** support with sheet picker  
- **Schema + sample rows** sent to the model for accurate code  
- **Safe execution** of generated `pandas` / `numpy` / `matplotlib` code (restricted builtins and imports)  
- **Charts** exported as PNG with optional downloads  
- **Try sample data** — no file required to explore the UI  
- **Export conversation** as Markdown from the sidebar  

## Configuration

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Required (or set in `.env` / Streamlit secrets on deploy) |
| `GEMINI_MODEL` | Optional; defaults to `gemini-2.0-flash` |

## Development

Run tests:

```bash
pytest tests -q
```

## Security note

This app executes **LLM-generated code** in a restricted in-process sandbox. Use only with data you trust; do not expose untrusted users to a public deployment without additional hardening.
