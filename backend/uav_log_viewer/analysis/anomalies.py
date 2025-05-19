from __future__ import annotations
"""LLM‑driven anomaly analysis (no rule‑based detectors).

Workflow
~~~~~~~~
1. **Intent filter** – quick regex check to see if the user is asking about
   anomalies / failures.
2. **Field extraction** – use Cohere semantic search to pull only the relevant
   fields for the question (reduces token usage).
3. **LLM reasoning** – prompt Groq‑Llama3 with the question + extracted fields;
   the model decides thresholds and reports anomalies, or politely asks for
   clarification if data is insufficient.

Public API
~~~~~~~~~~
```
from uav_log_viewer.analysis.anomalies import analyse_query
answer_or_none = analyse_query(question, telemetry_dict)
```
Returns a response **string** or `None` if the question is *not* anomaly‑related.
"""

from typing import Any, Dict, List
import os
import re
import json

from openai import OpenAI  # Groq client (OpenAI‑compatible)

from .data_extractor import DataExtractor

# ---------------------------------------------------------------------------
# 1. Intent filter
# ---------------------------------------------------------------------------
_ANOMALY_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"anomal(ies|y)", r"issue", r"problem", r"error", r"fail", r"lost", r"loss",
        r"glitch", r"drop", r"inconsisten(ce|t)", r"weird", r"abnormal", r"irregular",
    )
]

def is_anomaly_query(q: str) -> bool:
    return any(p.search(q) for p in _ANOMALY_PATTERNS)

# ---------------------------------------------------------------------------
# 2. Groq client helper
# ---------------------------------------------------------------------------
_GROQ_URL = os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1")
_GROQ_MODEL = os.getenv("GROQ_DEFAULT_MODEL", "llama3-70b-8192")

_client: OpenAI | None = None

def _groq() -> OpenAI:
    global _client
    if _client is None:
        key = os.getenv("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY not set in environment")
        _client = OpenAI(api_key=key, base_url=_GROQ_URL)
    return _client

# ---------------------------------------------------------------------------
# 3. Prompt builder (LLM decides thresholds)
# ---------------------------------------------------------------------------

def _json_short(obj: Any, max_len: int = 800) -> str:
    txt = json.dumps(obj, default=str, indent=2)
    if len(txt) <= max_len:
        return txt
    half = max_len // 2
    return txt[:half] + "\n… (truncated) …\n" + txt[-half:]


def _build_prompt(q: str, extracted: Dict[str, Any]) -> str:
    return "\n".join(
        [
            "You are an expert UAV telemetry analyst.",
            "User question: " + q,
            "\n## Extracted fields (JSON)\n" + _json_short(extracted),
            """
Instructions:
• Decide whether any value or pattern constitutes an anomaly. **Derive or cite a reasonable threshold** from UAV best‑practice or the data distribution itself.
• If the question is ambiguous or the data is insufficient, politely ask the user to clarify (metric, time window, etc.) before answering.
• Provide timestamps (seconds‑since‑boot) and offending values when relevant.
• If nothing is abnormal, state “No anomalies detected.”
• The <suggested_questions> block must include three user-phrased questions **that can be answered using the extracted data above**.

Use **this exact format**:
<answer>
Your response …
</answer>

<suggested_questions>
1. I'd like to examine another subsystem.
2. Could you plot the altitude vs time?
3. Please highlight any attitude spikes.
</suggested_questions>
""",
        ]
    )

# ---------------------------------------------------------------------------
# 4. Public orchestrator
# ---------------------------------------------------------------------------

def analyse_query(question: str, telemetry: Dict[str, Any]) -> str | None:
    """Return LLM‑generated anomaly answer, or None if not anomaly query."""
    if not is_anomaly_query(question):
        return None

    # Semantic field extraction (narrow context for LLM)
    extractor = DataExtractor()
    extracted = extractor.extract_relevant_data(telemetry, question, top_k=25, rerank=True)

    prompt = _build_prompt(question, extracted)

    resp = _groq().chat.completions.create(
        model=_GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=500,
    )
    return resp.choices[0].message.content.strip()
