from __future__ import annotations
"""Prompt building utilities

Creates instruction texts for Groq‑Llama depending on context:
• `build_metric_prompt()` – when we have extracted JSON + pre‑computed metrics.
• `build_general_prompt()` – when no telemetry context is available.

The LLM is expected to answer with two XML‑style blocks:
<answer> … </answer>
<suggested_questions> … </suggested_questions>
"""

from typing import Dict, Any, List, Optional
import json

# ---------------------------------------------------------------------------
# Helper – pretty‑print (truncated) JSON
# ---------------------------------------------------------------------------

def _json_short(obj: Any, *, max_len: int = 600) -> str:
    txt = json.dumps(obj, default=str, indent=2)
    if len(txt) <= max_len:
        return txt
    half = max_len // 2
    return txt[:half] + "\n… (truncated) …\n" + txt[-half:]

# ---------------------------------------------------------------------------
# Metric prompt (UAV log available)
# ---------------------------------------------------------------------------

def build_metric_prompt(question: str, extracted: Dict[str, Any], metrics: Dict[str, Any]) -> str:
    """Assemble prompt when telemetry context is present."""

    sys_prompt = (
        "You are an expert UAV telemetry analyst. If the question is ambiguous or a single token (e.g., \"max\"), "
        "**ask a concise clarification before proceeding**. Your tasks:\n"
        "1. Use the *metrics* and *raw field excerpts* below to answer the user.\n"
        "2. If a value is relevant, quote it (units included).\n"
        "3. Explain calculations only briefly when asked.\n"
        "4. If data is missing, say so and suggest what additional log fields are needed.\n"
        "5. Keep answers concise and technically precise.\n\n"
        "If, after inspecting the *metrics* and *extracted fields*, you **cannot confidently answer** "
        "(because the question is too vague or the requested signal is missing) then *do not guess* — "
        "instead, politely ask the user to clarify what specific metric, time‑window, or field they need.\n\n"
        "Use this exact output format:\n"
        "<answer>\nYour response here…\n</answer>\n\n"
        "<suggested_questions>\n"
        "1. Another meaningful follow‑up\n"
        "2. Deeper analysis request\n"
        "3. Potential anomaly check\n"
        "</suggested_questions>\n\n"
        "Inside <suggested_questions> generate THREE concise follow-up questions, phrased from the USER'S point of view, **and ensure each can be answered using the telemetry data already provided** (e.g., \"What is the max altitude?\")."
    )

    context_parts: List[str] = [
        "## Pre‑computed Metrics (key = value):\n",
        _json_short(metrics),
        "\n\n## Extracted Field Samples:\n",
        _json_short(extracted, max_len=800),
    ]

    return f"{sys_prompt}\n\n{''.join(context_parts)}\n\nUser question: {question}"

# ---------------------------------------------------------------------------
# General prompt (no UAV log yet or non‑UAV question)
# ---------------------------------------------------------------------------

def build_general_prompt(question: str) -> str:
    sys_prompt = (
        "You are a helpful assistant. If the user's question is too vague "
        "(e.g., single word like \"max\") or could mean multiple things, "
        "politely request clarification before answering. The user may or may not "
        "have uploaded a UAV log.\n"
        "• If the question is unrelated to UAV telemetry, answer normally.\n"
        "• If the user might benefit from uploading a flight log, gently mention that.\n\n"
        "Use the same XML blocks as above (<answer>, <suggested_questions>).\n"
        "Inside <suggested_questions> generate THREE UAV telemetry follow-up questions, phrased from the USER'S point of view, even for greetings like 'Hi'."
    )

    return f"{sys_prompt}\n\nUser question: {question}"

# ---------------------------------------------------------------------------
#  Post‑processing helper to split blocks
# ---------------------------------------------------------------------------

def extract_response_parts(response: str) -> Dict[str, Any]:
    parts = {"answer": "", "suggested_questions": []}

    if "<answer>" in response and "</answer>" in response:
        parts["answer"] = response.split("<answer>")[1].split("</answer>")[0].strip()

    if "<suggested_questions>" in response and "</suggested_questions>" in response:
        block = response.split("<suggested_questions>")[1].split("</suggested_questions>")[0]
        suggestions: List[str] = []
        import re
        for raw in block.strip().splitlines():
            line = raw.strip()
            if not line:
                continue
            # Remove common list prefixes like "1.", "-", "•"
            line = re.sub(r"^(\d+\.|[-•])\s*", "", line)
            suggestions.append(line)
        parts["suggested_questions"] = suggestions

    return parts
