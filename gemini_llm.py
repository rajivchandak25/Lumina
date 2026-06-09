"""
gemini_llm.py
─────────────
Wrapper around the Google Generative AI SDK.

Responsibilities:
  • Configure the Gemini client from environment variables
  • Build system-level + per-turn prompts for code generation
  • Self-healing retry: re-prompt with failed code + error context
  • Follow-up question generation (JSON output)
  • History pruning (sliding window, max 10 turns)
  • LLM-powered prediction and causal-analysis prompts
  • Extract the Python code block from the model's response
"""

from __future__ import annotations

import json
import os
import re
import textwrap
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

try:
    import google.generativeai as genai
    from google.generativeai.types import HarmBlockThreshold, HarmCategory
    _GENAI_IMPORT_ERROR: Exception | None = None
except Exception as exc:
    genai = None
    _GENAI_IMPORT_ERROR = exc

    class HarmBlockThreshold:  # fallback constants for helper-only imports/tests
        BLOCK_ONLY_HIGH = "BLOCK_ONLY_HIGH"
        BLOCK_NONE = "BLOCK_NONE"

    class HarmCategory:  # fallback constants for helper-only imports/tests
        HARM_CATEGORY_HARASSMENT = "HARM_CATEGORY_HARASSMENT"
        HARM_CATEGORY_HATE_SPEECH = "HARM_CATEGORY_HATE_SPEECH"
        HARM_CATEGORY_SEXUALLY_EXPLICIT = "HARM_CATEGORY_SEXUALLY_EXPLICIT"
        HARM_CATEGORY_DANGEROUS_CONTENT = "HARM_CATEGORY_DANGEROUS_CONTENT"

load_dotenv(Path(__file__).resolve().parent / ".env")

# ── Configuration ─────────────────────────────────────────────────────────────

_MODEL_NAME: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
_MAX_HISTORY_TURNS: int = int(
    os.getenv(
        "LUMINA_MAX_TURNS",
        os.getenv("EXCELCHAT_MAX_TURNS", "10"),
    )
)

_SAFETY_FOR_CODE_GEN: list[dict] = [
    {"category": HarmCategory.HARM_CATEGORY_HARASSMENT,        "threshold": HarmBlockThreshold.BLOCK_ONLY_HIGH},
    {"category": HarmCategory.HARM_CATEGORY_HATE_SPEECH,       "threshold": HarmBlockThreshold.BLOCK_ONLY_HIGH},
    {"category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, "threshold": HarmBlockThreshold.BLOCK_ONLY_HIGH},
    # Python/matplotlib/plotly is often misclassified as "dangerous"
    {"category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, "threshold": HarmBlockThreshold.BLOCK_NONE},
]

_SAFETY_RELAXED: list[dict] = [
    {"category": HarmCategory.HARM_CATEGORY_HARASSMENT,        "threshold": HarmBlockThreshold.BLOCK_ONLY_HIGH},
    {"category": HarmCategory.HARM_CATEGORY_HATE_SPEECH,       "threshold": HarmBlockThreshold.BLOCK_ONLY_HIGH},
    {"category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, "threshold": HarmBlockThreshold.BLOCK_ONLY_HIGH},
    {"category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, "threshold": HarmBlockThreshold.BLOCK_ONLY_HIGH},
]


# ── System prompts ────────────────────────────────────────────────────────────

_CODE_GEN_SYSTEM_PROMPT = textwrap.dedent("""
    You are Lumina, an expert data analyst assistant.
    You receive a description of an Excel dataset (column names, dtypes, sample rows)
    and a natural-language question from the user.

    Your ONLY job is to write a single, self-contained Python code block that:
      1. Uses the variable `df` (a pre-loaded pandas DataFrame) to answer the question.
      2. Stores the final result in a variable called `result`.
         • If the answer is a single value or text → `result` = str / number
         • If the answer is a table              → `result` = pandas DataFrame
         • If the answer is a chart              → `result` = Plotly Figure (preferred) or matplotlib Figure
      3. Does NOT import pandas, numpy, plotly or matplotlib — they are pre-injected:
             import pandas as pd
             import numpy as np
             import matplotlib; import matplotlib.pyplot as plt
             import plotly.express as px
             import plotly.graph_objects as go
      4. Does NOT read files, access the network, or use `input()`.
      5. Is clearly commented so a beginner can follow the logic.

    ── Chart guidelines ─────────────────────────────────────────────────────────
    PREFER Plotly for all charts. Use px.bar(), px.line(), px.scatter(),
    px.histogram(), px.box(), px.imshow() (for heatmaps / correlation matrices).

    For Plotly charts:
      • result = px.bar(df, x="col", y="col", title="...") — assign the Figure directly.
      • Apply the dark theme:
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="#0d1117",
                plot_bgcolor="#161b22",
                font=dict(color="#e6edf3"),
            )
      • Do NOT call .show().
      • result = fig  (always the Figure object)

    Fallback to matplotlib ONLY for complex multi-subplot layouts Plotly cannot represent:
      • Use `fig, ax = plt.subplots(figsize=(10, 5))` for matplotlib chart creation.
      • Always label axes and add a title.
      • Call `plt.tight_layout()` before assigning `result`.
      • Do NOT call `plt.show()`.
      • Set `result = fig` (not `result = ax`).

    ── Output format ────────────────────────────────────────────────────────────
    Return ONLY a fenced Python code block, like this:

    ```python
    # Your code here
    result = ...
    ```

    Do NOT add prose before or after the code block.
    If the question cannot be answered with the available data, set:
        result = "I'm sorry, I cannot answer that question with the available data."
""").strip()


_ANALYSIS_SYSTEM_PROMPT = textwrap.dedent("""
    You are a quantitative data analyst. You will receive a dataset schema and
    statistical summary. Your task is to provide structured, actionable insights.
    Cite specific column names and values from the schema.
    Do NOT generate code. Do NOT invent data not present in the schema.
    Be concise and specific.
""").strip()


# ── Public API ────────────────────────────────────────────────────────────────

class GeminiLLM:
    """LLM client for Lumina — code generation, retry, follow-ups, analysis."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        if genai is None:
            raise ImportError(
                "google-generativeai is not installed. Install requirements.txt dependencies "
                "to enable Gemini-powered features."
            ) from _GENAI_IMPORT_ERROR

        key = api_key or os.getenv("GEMINI_API_KEY", "")
        if not key:
            raise ValueError("GEMINI_API_KEY is not set.")

        genai.configure(api_key=key)

        # Model for code generation
        self._code_model = genai.GenerativeModel(
            model_name=_MODEL_NAME,
            system_instruction=_CODE_GEN_SYSTEM_PROMPT,
            safety_settings=_SAFETY_FOR_CODE_GEN,
            generation_config=genai.GenerationConfig(
                temperature=0.1,
                max_output_tokens=8192,
            ),
        )

        # Separate model for analysis (predictions, causes, follow-ups)
        self._analysis_model = genai.GenerativeModel(
            model_name=_MODEL_NAME,
            system_instruction=_ANALYSIS_SYSTEM_PROMPT,
            safety_settings=_SAFETY_RELAXED,
            generation_config=genai.GenerationConfig(
                temperature=0.3,
                max_output_tokens=4096,
            ),
        )

    # ── Code generation ───────────────────────────────────────────────────────

    def generate_code(
        self,
        schema_description: str,
        sample_rows: str,
        user_question: str,
        chat_history: Optional[list[dict]] = None,
    ) -> str:
        """
        Ask Gemini to write Python/Pandas/Plotly code that answers *user_question*.

        Parameters
        ----------
        schema_description : str  Output of ``excel_processor.build_schema_description()``.
        sample_rows        : str  Markdown table with first 5 rows.
        user_question      : str  The user's natural-language question.
        chat_history       : list[dict]  Previous turns (pruned automatically).

        Returns
        -------
        str  Raw text response from Gemini (contains a ```python … ``` block).
        """
        user_message = _build_user_message(schema_description, sample_rows, user_question)
        pruned = _prune_history(chat_history or [])
        history = _format_history(pruned)

        chat = self._code_model.start_chat(history=history)
        response = chat.send_message(user_message, safety_settings=_SAFETY_FOR_CODE_GEN)
        return _response_text_safe(response)

    def generate_retry(
        self,
        original_question: str,
        failed_code: str,
        error_message: str,
        schema_description: str,
        sample_rows: str,
    ) -> str:
        """
        Re-prompt Gemini with the failed code + error, asking for a corrected version.
        Uses a fresh chat (no history) to avoid confusing the model.
        """
        retry_message = _build_retry_message(
            original_question, failed_code, error_message, schema_description, sample_rows
        )
        chat = self._code_model.start_chat(history=[])
        response = chat.send_message(retry_message, safety_settings=_SAFETY_FOR_CODE_GEN)
        return _response_text_safe(response)

    # ── Follow-up questions ───────────────────────────────────────────────────

    def generate_followups(
        self,
        schema_description: str,
        last_question: str,
        last_answer_summary: str,
    ) -> list[str]:
        """
        Generate 3 suggested follow-up questions for the user.

        Returns a list of up to 3 strings. Returns [] on any failure so
        the caller never has to handle errors from this method.
        """
        prompt = textwrap.dedent(f"""
            Dataset schema:
            {schema_description}

            The user just asked: "{last_question}"
            The answer summary: "{last_answer_summary}"

            Suggest exactly 3 concise follow-up questions the user might want to ask next.
            Return ONLY a JSON array of 3 strings, no prose, no explanation:
            ["question 1", "question 2", "question 3"]
        """).strip()

        try:
            chat = self._analysis_model.start_chat(history=[])
            response = chat.send_message(prompt, safety_settings=_SAFETY_RELAXED)
            text = _response_text_safe(response).strip()
            # Extract JSON array (may be wrapped in markdown)
            match = re.search(r'\[.*?\]', text, re.DOTALL)
            if match:
                questions = json.loads(match.group())
                if isinstance(questions, list):
                    return [str(q) for q in questions[:3]]
        except Exception:
            pass
        return []

    # ── Predictions & Causes ──────────────────────────────────────────────────

    def generate_predictions(
        self,
        schema_description: str,
        statistical_summary: str,
    ) -> str:
        """
        Generate LLM-powered trend predictions for the dataset.
        Returns formatted markdown with structured prediction cards.
        """
        prompt = textwrap.dedent(f"""
            ## Dataset Schema
            {schema_description}

            ## Statistical Summary
            {statistical_summary}

            ## Task
            Identify 3–5 actionable trends or patterns that are likely to continue,
            and state what predictions can be made from this data.

            Format your response as structured insight cards using EXACTLY this markdown:

            ### Prediction 1: [Short descriptive title]
            **Confidence:** High / Medium / Low
            **Evidence:** [What in the data supports this — cite column names and values]
            **Forecast:** [What is likely to happen or continue]

            Repeat for each prediction (maximum 5). Be specific. Do NOT generate code.
        """).strip()

        chat = self._analysis_model.start_chat(history=[])
        response = chat.send_message(prompt, safety_settings=_SAFETY_RELAXED)
        return _response_text_safe(response)

    def generate_causes(
        self,
        schema_description: str,
        statistical_summary: str,
        top_correlations: str,
    ) -> str:
        """
        Generate LLM-powered causal factor analysis for the dataset.
        Returns formatted markdown with structured cause cards.
        """
        prompt = textwrap.dedent(f"""
            ## Dataset Schema
            {schema_description}

            ## Statistical Summary
            {statistical_summary}

            ## Top Correlated Column Pairs
            {top_correlations}

            ## Task
            Identify the most likely driving factors behind the patterns in this data.
            Maximum 4 factors. Cite real column names and correlation evidence.

            Format as structured cards using EXACTLY this markdown:

            ### Factor 1: [Short descriptive title]
            **Affected metric:** [column name]
            **Likely driver:** [explanation referencing real column names from the schema]
            **Supporting signal:** [correlation or distribution evidence from the summary]

            Repeat for each factor. Do NOT generate code.
        """).strip()

        chat = self._analysis_model.start_chat(history=[])
        response = chat.send_message(prompt, safety_settings=_SAFETY_RELAXED)
        return _response_text_safe(response)

    # ── Convenience ───────────────────────────────────────────────────────────

    def extract_code(self, llm_response: str) -> Optional[str]:
        """Pull the Python code out of the fenced block in *llm_response*."""
        return _extract_code_block(llm_response)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _prune_history(history: list[dict], max_turns: int = _MAX_HISTORY_TURNS) -> list[dict]:
    """
    Keep the last *max_turns* user+assistant pairs (sliding window).
    Always returns an even-length slice to preserve conversation parity.
    """
    if len(history) <= max_turns * 2:
        return history
    return history[-(max_turns * 2):]


def _response_text_safe(response: Any) -> str:
    """
    Prefer `response.text`; if blocked or empty, return a clear fallback message.
    """
    try:
        pf = response.prompt_feedback
        if pf is not None and getattr(pf, "block_reason", None):
            return (
                "The prompt was blocked by the API before generation could run "
                f"(reason: {pf.block_reason}). Try rephrasing your question."
            )
    except (AttributeError, ValueError):
        pass

    try:
        text = response.text
        if text is not None and str(text).strip():
            return text
    except ValueError:
        pass

    cands = list(response.candidates) if getattr(response, "candidates", None) else []
    if not cands:
        return (
            "The model returned no output. This is often due to response-level safety filters "
            "on charts or code. Try asking again, or shorten the question."
        )

    c0 = cands[0]
    chunks: list[str] = []
    if c0.content and c0.content.parts:
        for part in c0.content.parts:
            t = getattr(part, "text", None)
            if t:
                chunks.append(t)
    if chunks:
        return "".join(chunks)

    fr = getattr(c0, "finish_reason", None)
    ratings = getattr(c0, "safety_ratings", None) or []
    detail = ", ".join(
        f"{getattr(r, 'category', '?')}={getattr(r, 'probability', '?')}" for r in ratings
    )
    return (
        "The model did not return usable text (often blocked as code/chart output). "
        f"finish_reason={fr}. "
        + (f"Ratings: [{detail}]. " if detail else "")
        + "Try rephrasing or ask for a table instead of a chart first."
    )


def _build_user_message(schema: str, sample: str, question: str) -> str:
    return textwrap.dedent(f"""
        ## Dataset Schema
        {schema}

        ## Sample Rows (first 5)
        {sample}

        ## Question
        {question}
    """).strip()


def _build_retry_message(
    original_question: str,
    failed_code: str,
    error_message: str,
    schema: str,
    sample: str,
) -> str:
    return textwrap.dedent(f"""
        ## Dataset Schema
        {schema}

        ## Sample Rows (first 5)
        {sample}

        ## Original Question
        {original_question}

        ## Previous Code Attempt (FAILED — do NOT repeat this)
        ```python
        {failed_code}
        ```

        ## Execution Error
        ```
        {error_message}
        ```

        ## Task
        The previous code raised the error above. Write a CORRECTED version.
        Fix only the error. Keep the same goal. Return only a ```python block.
    """).strip()


def _format_history(history: list[dict]) -> list[dict]:
    """
    Convert internal chat history to Gemini's expected format.
    Internal: [{"role": "user"|"assistant", "content": "..."}]
    Gemini:   [{"role": "user"|"model",     "parts": ["..."]}]
    """
    formatted = []
    for turn in history:
        role = "model" if turn.get("role") == "assistant" else "user"
        content = turn.get("content", "")
        if content:
            formatted.append({"role": role, "parts": [content]})
    return formatted


def _extract_code_block(text: str) -> Optional[str]:
    """
    Extract the contents of the first ```python … ``` block in *text*.
    Falls back to any ``` … ``` block if no language tag is present.
    """
    match = re.search(r"```python\s*\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    match = re.search(r"```\s*\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    return None
