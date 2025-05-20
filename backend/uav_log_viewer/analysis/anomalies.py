# from __future__ import annotations
# """LLM‑driven anomaly analysis (no rule‑based detectors).

# Workflow
# ~~~~~~~~
# 1. **Intent filter** – quick regex check to see if the user is asking about
#    anomalies / failures.
# 2. **Field extraction** – use Cohere semantic search to pull only the relevant
#    fields for the question (reduces token usage).
# 3. **LLM reasoning** – prompt Groq‑Llama3 with the question + extracted fields;
#    the model decides thresholds and reports anomalies, or politely asks for
#    clarification if data is insufficient.

# Public API
# ~~~~~~~~~~
# ```
# from uav_log_viewer.analysis.anomalies import analyse_query
# answer_or_none = analyse_query(question, telemetry_dict)
# ```
# Returns a response **string** or `None` if the question is *not* anomaly‑related.
# """

# from typing import Any, Dict, List
# import os
# import re
# import json

# from openai import OpenAI  # Groq client (OpenAI‑compatible)

# from .data_extractor import DataExtractor
# from uav_log_viewer.analysis import compute_metrics  # flight-level summaries

# # ---------------------------------------------------------------------------
# # 1. Intent filter
# # ---------------------------------------------------------------------------
# _ANOMALY_PATTERNS = [
#     re.compile(p, re.I)
#     for p in (
#         r"anomal(ies|y)", r"issue", r"problem", r"error", r"fail", r"lost", r"loss",
#         r"glitch", r"drop", r"inconsisten(ce|t)", r"weird", r"abnormal", r"irregular",
#     )
# ]

# def is_anomaly_query(q: str) -> bool:
#     return any(p.search(q) for p in _ANOMALY_PATTERNS)

# # ---------------------------------------------------------------------------
# # 2. Groq client helper
# # ---------------------------------------------------------------------------
# _GROQ_URL = os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1")
# _GROQ_MODEL = os.getenv("GROQ_DEFAULT_MODEL", "llama3-70b-8192")

# _client: OpenAI | None = None

# def _groq() -> OpenAI:
#     global _client
#     if _client is None:
#         key = os.getenv("GROQ_API_KEY")
#         if not key:
#             raise RuntimeError("GROQ_API_KEY not set in environment")
#         _client = OpenAI(api_key=key, base_url=_GROQ_URL)
#     return _client

# # ---------------------------------------------------------------------------
# # 3. Prompt builder (LLM decides thresholds)
# # ---------------------------------------------------------------------------

# def _json_short(obj: Any, max_len: int = 800) -> str:
#     txt = json.dumps(obj, default=str, indent=2)
#     if len(txt) <= max_len:
#         return txt
#     half = max_len // 2
#     return txt[:half] + "\n… (truncated) …\n" + txt[-half:]


# def _build_prompt(q: str, extracted: Dict[str, Any], metrics: Dict[str, Any]) -> str:
#     """Assemble prompt for anomaly questions (LLM-only).

#     The prompt now includes *pre-computed metrics* first, followed by the
#     semantic-search field excerpts. This gives the LLM useful global context
#     even for vague questions like "Any anomalies?".
#     """

#     sys_prompt = (
#         "You are an expert UAV telemetry analyst. "
#         "If the question is ambiguous or the data is insufficient, "
#         "**ask a concise clarification before proceeding**.\n\n"
#         "Instructions:\n"
#         "• Decide whether any value or pattern constitutes an anomaly. "
#         "**Derive or cite a reasonable threshold** from UAV best-practice or the data distribution itself.\n"
#         "• Provide timestamps (seconds-since-boot) and offending values when relevant.\n"
#         "• If nothing is abnormal, state \"No anomalies detected.\"\n"
#         "• The <suggested_questions> block must include three user-phrased questions "
#         "**that can be answered using the extracted data below**.\n\n"
#         "Use this exact output format:\n"
#         "<answer>\nYour response …\n</answer>\n\n"
#         "<suggested_questions>\n"
#         "1. I'd like to examine another subsystem.\n"
#         "2. Could you plot the altitude vs time?\n"
#         "3. Please highlight any attitude spikes.\n"
#         "</suggested_questions>\n\n"
#         "Inside <suggested_questions> generate THREE UAV telemetry follow-up questions, phrased from the USER'S point of view."
#     )

#     context_parts: List[str] = [
#         "## Pre-computed Metrics (key = value)\n",
#         _json_short(metrics, max_len=600),
#         "\n\n## Extracted fields (JSON)\n",
#         _json_short(extracted),
#     ]

#     return f"{sys_prompt}\n\n{''.join(context_parts)}\n\nUser question: {q}"

# # ---------------------------------------------------------------------------
# # 4. Public orchestrator
# # ---------------------------------------------------------------------------

# def analyse_query(question: str, telemetry: Dict[str, Any]) -> str | None:
#     """Return LLM‑generated anomaly answer, or None if not anomaly query."""
#     if not is_anomaly_query(question):
#         return None

#     # Semantic field extraction (narrow context for LLM)
#     extractor = DataExtractor()
#     extracted = extractor.extract_relevant_data(telemetry, question, top_k=25, rerank=True)

#     # Compute flight-level summaries regardless of question specificity.
#     metrics = compute_metrics(telemetry)

#     prompt = _build_prompt(question, extracted, metrics)

#     resp = _groq().chat.completions.create(
#         model=_GROQ_MODEL,
#         messages=[{"role": "user", "content": prompt}],
#         temperature=0.2,
#         max_tokens=500,
#     )
#     return resp.choices[0].message.content.strip()

"""
anomalies.py – LLM-driven anomaly analysis for UAV telemetry
============================================================

Workflow
--------
1. *Intent filter* – regex check to see whether the user is asking about anomalies.
2. *Field extraction* – Cohere semantic search keeps only fields relevant to the question.
3. *Primitive flags* – `highlight_anomalies()` does quick rule-based scans
   (z-score spikes, low GPS satellites, battery sag, high vibration).
4. *LLM reasoning* – Prompt Groq-Llama-3 with:
      • pre-computed flight metrics
      • primitive flags (as hints)
      • extracted field samples
   The model decides thresholds, reports anomalies, or asks for clarification.

Public API
----------
    from uav_log_viewer.analysis.anomalies import analyse_query
    reply_or_none = analyse_query(question, telemetry_dict)
"""

from __future__ import annotations

from typing import Any, Dict, List
import os
import re
import json

import numpy as np
from openai import OpenAI  # Groq client (OpenAI-compatible)

from .data_extractor import DataExtractor
from .telemetry import compute_metrics

# ────────────────────────────────────────────────────────────────
# 1. Intent filter
# ────────────────────────────────────────────────────────────────
_ANOMALY_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"anomal(ies|y)", r"issue", r"problem", r"error",
        r"fail", r"fault", r"lost", r"loss", r"glitch",
        r"drop", r"inconsisten(ce|t)", r"weird", r"abnormal",
        r"irregular", r"off-nominal",
    )
]


def is_anomaly_query(q: str) -> bool:
    """Return True if question *q* looks like an anomaly/failure query."""
    return any(p.search(q) for p in _ANOMALY_PATTERNS)


# ────────────────────────────────────────────────────────────────
# 2. Groq client helper
# ────────────────────────────────────────────────────────────────
_GROQ_URL = os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1")
_GROQ_MODEL = os.getenv("GROQ_DEFAULT_MODEL", "llama3-70b-8192")

_client: OpenAI | None = None


def _groq() -> OpenAI:
    global _client
    if _client is None:
        key = os.getenv("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY not set")
        _client = OpenAI(api_key=key, base_url=_GROQ_URL)
    return _client


# ────────────────────────────────────────────────────────────────
# 3. Primitive anomaly detector (rule-based, cheap)
# ────────────────────────────────────────────────────────────────
def highlight_anomalies(telemetry: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Return a *list of flag dicts* describing obvious anomalies.
    These are passed to the LLM as initial hints.
    """
    anomalies: List[Dict[str, Any]] = []

    def z_outliers(name: str, array: List[float], threshold: float = 2.5) -> None:
        if len(array) < 5:
            return
        arr = np.asarray(array, dtype=np.float32)
        std = arr.std() + 1e-6
        z_scores = np.abs((arr - arr.mean()) / std)
        for idx in np.where(z_scores > threshold)[0]:
            anomalies.append(
                {
                    "feature": name,
                    "index": int(idx),
                    "value": float(arr[idx]),
                    "pattern": "z-score",
                    "hint": f"Unusual {name} value {arr[idx]:.2f} at index {idx}",
                }
            )

    msgs = telemetry.get("messages", {})

    # Attitude spikes
    if "ATTITUDE" in msgs:
        for field in ("roll", "pitch", "yaw"):
            if field in msgs["ATTITUDE"]:
                z_outliers(f"attitude.{field}", msgs["ATTITUDE"][field])

    # Position / velocity spikes
    if "GLOBAL_POSITION_INT" in msgs:
        for field in ("alt", "relative_alt", "vx", "vy", "vz"):
            if field in msgs["GLOBAL_POSITION_INT"]:
                z_outliers(f"position.{field}", msgs["GLOBAL_POSITION_INT"][field])

    # GPS satellite count
    if "GPS_RAW_INT" in msgs and "satellites_visible" in msgs["GPS_RAW_INT"]:
        for idx, val in enumerate(msgs["GPS_RAW_INT"]["satellites_visible"]):
            if val < 6:
                anomalies.append(
                    {
                        "feature": "gps.satellites_visible",
                        "index": idx,
                        "value": int(val),
                        "pattern": "low_satellites",
                        "hint": f"Only {val} satellites at index {idx}; GPS may be unreliable",
                    }
                )

    # Battery sag (< 3.4 V per cell)
    if "BATTERY_STATUS" in msgs and "voltages" in msgs["BATTERY_STATUS"]:
        for idx, mv in enumerate(msgs["BATTERY_STATUS"]["voltages"]):
            if mv is None:
                continue
            volts = mv / 1000.0
            if volts < 3.4:
                anomalies.append(
                    {
                        "feature": "battery.voltage",
                        "index": idx,
                        "value": volts,
                        "pattern": "voltage_sag",
                        "hint": f"Cell voltage dropped to {volts:.2f} V (index {idx})",
                    }
                )

    # High vibration RMS (> 30 m/s²)
    if "VIBRATION" in msgs and {"vibration_x", "vibration_y", "vibration_z"} <= msgs["VIBRATION"].keys():
        vx = np.asarray(msgs["VIBRATION"]["vibration_x"], dtype=np.float32)
        vy = np.asarray(msgs["VIBRATION"]["vibration_y"], dtype=np.float32)
        vz = np.asarray(msgs["VIBRATION"]["vibration_z"], dtype=np.float32)
        if len(vx) > 0:
            rms = np.sqrt(vx**2 + vy**2 + vz**2)
            for idx, val in enumerate(rms):
                if val > 30.0:  # m/s²
                    anomalies.append(
                        {
                            "feature": "vibration.rms",
                            "index": idx,
                            "value": float(val),
                            "pattern": "high_vibration",
                            "hint": f"High vibration RMS {val:.1f} m/s² at index {idx}",
                        }
                    )

    return anomalies


# ────────────────────────────────────────────────────────────────
# 4. Prompt helpers
# ────────────────────────────────────────────────────────────────
def _json_short(obj: Any, max_len: int = 800) -> str:
    txt = json.dumps(obj, default=str, indent=2)
    if len(txt) <= max_len:
        return txt
    half = max_len // 2
    return txt[:half] + "\n… (truncated) …\n" + txt[-half:]


def _build_prompt(
    q: str,
    extracted: Dict[str, Any],
    metrics: Dict[str, Any],
    primitive_flags: List[Dict[str, Any]],
) -> str:
    """
    Construct system prompt + context for Groq-Llama-3.
    """
    sys_prompt = (
        "You are an expert UAV telemetry analyst. "
        "If the question is ambiguous or the data is insufficient, "
        "ask a concise clarification before proceeding.\n\n"
        "Instructions:\n"
        "• Decide whether any value or pattern constitutes an anomaly.\n"
        "• Derive or cite a reasonable threshold from UAV best-practice or the data distribution itself.\n"
        "• Quote timestamps (seconds-since-boot) and offending values.\n"
        "• If nothing is abnormal, state \"No anomalies detected.\"\n"
        "• After answering, return THREE first-person follow-up questions that can be answered with the data below.\n\n"
        "Output format:\n"
        "<answer>\n…\n</answer>\n\n"
        "<suggested_questions>\n"
        "1. …\n2. …\n3. …\n"
        "</suggested_questions>"
    )

    context: List[str] = [
        "## Flight-level metrics\n",
        _json_short(metrics, 500),
        "\n\n## Primitive anomaly flags (hints)\n",
        _json_short(primitive_flags, 400) if primitive_flags else "None\n",
        "\n\n## Extracted field samples\n",
        _json_short(extracted, 800),
    ]

    return f"{sys_prompt}\n\n{''.join(context)}\n\nUser question: {q}"


# ────────────────────────────────────────────────────────────────
# 5. Public entry – analyse_query
# ────────────────────────────────────────────────────────────────
def analyse_query(question: str, telemetry: Dict[str, Any]) -> str | None:
    """
    Return LLM result **if** the question is anomaly-related,
    otherwise return None so the caller can fall back to metric/general paths.
    """
    if not is_anomaly_query(question):
        return None

    # 1. Relevant fields via semantic search
    extractor = DataExtractor()
    extracted = extractor.extract_relevant_data(
        telemetry, question, top_k=25, rerank=True
    )

    # 2. Flight-level metrics for extra context
    metrics = compute_metrics(telemetry)

    # 3. Primitive flags
    primitive_flags = highlight_anomalies(telemetry)

    # 4. Prompt and LLM call
    prompt = _build_prompt(question, extracted, metrics, primitive_flags)

    resp = _groq().chat.completions.create(
        model=_GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=512,
    )
    return resp.choices[0].message.content.strip()

