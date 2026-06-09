"""
tests/test_gemini_llm.py
────────────────────────
Tests for gemini_llm module helpers (no live API calls):
  • _prune_history sliding window
  • _build_retry_message content
  • _extract_code_block edge cases
  • _format_history role mapping
"""

from __future__ import annotations

import pytest

# Import private helpers directly for unit testing
from gemini_llm import (
    _extract_code_block,
    _format_history,
    _prune_history,
    _build_retry_message,
)


# ── _prune_history ────────────────────────────────────────────────────────────

def test_prune_history_no_op_when_short():
    hist = [
        {"role": "user",      "content": "Q1"},
        {"role": "assistant", "content": "A1"},
    ]
    result = _prune_history(hist, max_turns=5)
    assert result == hist


def test_prune_history_keeps_last_n_pairs():
    # 12 turns (6 pairs) with max_turns=4 should keep last 8 entries (4 pairs)
    hist = []
    for i in range(6):
        hist.append({"role": "user",      "content": f"Q{i}"})
        hist.append({"role": "assistant", "content": f"A{i}"})

    result = _prune_history(hist, max_turns=4)
    assert len(result) == 8
    assert result[0]["content"] == "Q2"   # first kept user turn is Q2


def test_prune_history_exact_boundary():
    hist = []
    for i in range(5):
        hist.append({"role": "user",      "content": f"Q{i}"})
        hist.append({"role": "assistant", "content": f"A{i}"})

    # Exactly 5 pairs, max=5 → no pruning
    result = _prune_history(hist, max_turns=5)
    assert len(result) == 10


def test_prune_history_empty():
    assert _prune_history([], max_turns=5) == []


# ── _extract_code_block ───────────────────────────────────────────────────────

def test_extract_python_block():
    text = "Here is the code:\n```python\nresult = df.head()\n```"
    code = _extract_code_block(text)
    assert code == "result = df.head()"


def test_extract_bare_fence():
    text = "```\nresult = 42\n```"
    code = _extract_code_block(text)
    assert code == "result = 42"


def test_extract_no_code_block():
    text = "I cannot answer that question."
    code = _extract_code_block(text)
    assert code is None


def test_extract_first_block_when_multiple():
    text = "```python\nresult = 1\n```\n```python\nresult = 2\n```"
    code = _extract_code_block(text)
    assert code == "result = 1"


def test_extract_strips_whitespace():
    text = "```python\n\n   result = df.shape[0]   \n\n```"
    code = _extract_code_block(text)
    assert code == "result = df.shape[0]"


# ── _format_history ───────────────────────────────────────────────────────────

def test_format_history_maps_assistant_to_model():
    hist = [
        {"role": "user",      "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
    ]
    fmt = _format_history(hist)
    assert fmt[0]["role"] == "user"
    assert fmt[1]["role"] == "model"


def test_format_history_preserves_content():
    hist = [{"role": "user", "content": "Test question"}]
    fmt = _format_history(hist)
    assert fmt[0]["parts"] == ["Test question"]


def test_format_history_skips_empty_content():
    hist = [{"role": "user", "content": ""}]
    fmt = _format_history(hist)
    assert fmt == []


def test_format_history_empty_input():
    assert _format_history([]) == []


# ── _build_retry_message ─────────────────────────────────────────────────────

def test_retry_message_contains_original_question():
    msg = _build_retry_message(
        original_question="What is the total revenue?",
        failed_code="result = df['revenue'].sum()",
        error_message="KeyError: 'revenue'",
        schema="Sheet: Sales\nColumns: amount (float64)",
        sample="| amount |\n|--------|",
    )
    assert "What is the total revenue?" in msg


def test_retry_message_contains_failed_code():
    msg = _build_retry_message(
        original_question="Q",
        failed_code="result = df['bad_col']",
        error_message="KeyError: 'bad_col'",
        schema="Sheet: S",
        sample="",
    )
    assert "result = df['bad_col']" in msg


def test_retry_message_contains_error():
    msg = _build_retry_message(
        original_question="Q",
        failed_code="x = 1",
        error_message="ZeroDivisionError: division by zero",
        schema="Sheet: S",
        sample="",
    )
    assert "ZeroDivisionError" in msg
