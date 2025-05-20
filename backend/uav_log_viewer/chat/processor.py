"""
processor.py  –  orchestrates:
  • anomaly reasoning (analyse_query)
  • metric Q&A (semantic extraction + compute_metrics)
  • general chat fallback
and maintains conversation memory.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import os
import re

from openai import OpenAI                                     # Groq-compatible
from uav_log_viewer.analysis import (
    analyse_query,                                            # anomaly path
    compute_metrics,                                          # pre-calculations
    DataExtractor,                                            # semantic selector
)
from .prompt import (
    build_metric_prompt,
    build_general_prompt,
    extract_response_parts,
)
from .conversation import conversation_state                  # memory singleton


# --------------------------------------------------------------------------- #
# Groq Llama client (OpenAI-compatible)
# --------------------------------------------------------------------------- #

_GROQ_URL   = os.getenv("GROQ_API_BASE",   "https://api.groq.com/openai/v1")
_GROQ_MODEL = os.getenv("GROQ_DEFAULT_MODEL", "llama3-70b-8192")
_client: Optional[OpenAI] = None


def _llm() -> OpenAI:
    global _client
    if _client is None:
        key = os.getenv("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY not set")
        _client = OpenAI(api_key=key, base_url=_GROQ_URL)
    return _client


# --------------------------------------------------------------------------- #
# simple heuristic – does the question reference UAV telemetry terms?
# --------------------------------------------------------------------------- #

_UAV_PATTERNS = re.compile(
    r"altitude|\balt\b|pitch|roll|yaw|gps|rc|flight|telemetry|mavlink|"
    r"battery|groundspeed|descent|climb|satellite",
    re.I,
)


def _is_uav_question(q: str) -> bool:
    return bool(_UAV_PATTERNS.search(q))


# --------------------------------------------------------------------------- #
# helper – inject last 3 turns into prompt
# --------------------------------------------------------------------------- #

def _inject_history(prompt: str) -> str:
    tail = conversation_state.tail(3)
    if not tail:
        return prompt
    lines = ["## Recent conversation (last 3 turns):"]
    for msg in tail:
        lines.append(f"{msg['role'].capitalize()}: {msg['content']}")
    lines.append("")                       # trailing newline
    block = "\n".join(lines)
    # Insert right before the final 'User question:' tag
    return prompt.replace("User question:", f"{block}\nUser question:")


# --------------------------------------------------------------------------- #
# main API – called by FastAPI route
# --------------------------------------------------------------------------- #

def process_chat_request(question: str, telemetry: Dict[str, Any] | None) -> Dict[str, Any]:
    """Return assistant answer and suggested follow-up questions."""

    # 1) log user turn
    conversation_state.append("user", question)

    # 2) anomaly fast-path
    if telemetry is not None:
        anomaly_answer = analyse_query(question, telemetry)
        if anomaly_answer is not None:
            # Split the LLM response into <answer> / <suggested_questions>
            try:
                parts = extract_response_parts(anomaly_answer)
                answer_text = parts["answer"] or anomaly_answer
                suggestions = parts["suggested_questions"]
            except Exception:
                # Fallback – treat everything as the answer
                answer_text = anomaly_answer
                suggestions = []

            conversation_state.append("assistant", answer_text)
            return {"answer": answer_text, "suggested_questions": suggestions}

    # 3) UAV metric Q&A
    if telemetry is not None and _is_uav_question(question):
        extractor  = DataExtractor()
        extracted  = extractor.extract_relevant_data(
            telemetry, question, top_k=15, rerank=True
        )
        metrics    = compute_metrics(telemetry)
        prompt     = build_metric_prompt(question, extracted, metrics)
        prompt     = _inject_history(prompt)

    else:
        # 4) general chat fallback
        prompt = build_general_prompt(question)
        prompt = _inject_history(prompt)

    # 5) LLM call
    resp = _llm().chat.completions.create(
        model=_GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=400,
    )
    raw_answer = resp.choices[0].message.content.strip()

    # 6) parse structured blocks
    try:
        parts = extract_response_parts(raw_answer)
        answer_text = parts["answer"] or raw_answer
        suggestions = parts["suggested_questions"]
    except Exception:
        answer_text = raw_answer
        suggestions = []

    # 7) save assistant turn and return
    conversation_state.append("assistant", answer_text)
    return {"answer": answer_text, "suggested_questions": suggestions}

