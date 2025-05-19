from __future__ import annotations
"""Data Extractor
=================
Modern replacement for the previous hard‑coded keyword + `sentence_transformers` logic.
This version relies on **Cohere Semantic Search** to match user questions to telemetry
fields and (optionally) a rerank step to further refine matches.

* Requirements
  - `cohere>=4.43`  (`pip install cohere`)
  - `numpy`
  - `python-dotenv` (optional, if you want to load COHERE_API_KEY from a .env file)
* Environment variable
  - ``COHERE_API_KEY`` must be set with a valid key.

Usage Example
-------------
```python
from data_extractor import DataExtractor
extractor = DataExtractor()
fields = extractor.extract_relevant_data(telemetry_dict, question="What was the max altitude and how many satellites were visible?")
print(extractor.summarize(fields))
```
"""

from typing import Any, Dict, List, Set, Tuple
import os
import functools
import numpy as np

import cohere  # type: ignore

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def cosine_similarity_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Return an (m × n) matrix of cosine similarities between each row in *a* and *b*.

    Both *a* and *b* must be 2‑D (m × d) and (n × d).
    """
    # Normalize rows to unit length to make dot‑product the cosine similarity.
    a_norm = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-8)
    b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-8)
    return a_norm @ b_norm.T  # (m × n)


class DataExtractor:
    """Telemetry extractor that uses **Cohere embeddings** for semantic search.

    The extractor builds an *in‑memory* embedding index of every field path it
    discovers in the supplied telemetry structure and ranks them against the
    user question. The top‑k (configurable) high‑similarity fields are returned
    as a nested dict preserving the original hierarchy.

    Optionally, a **rerank** call can be used for higher precision. Enable it by
    passing ``rerank=True`` when calling :py:meth:`extract_relevant_data`.
    """

    def __init__(self, *, embed_model: str = "embed-english-v3.0", rerank_model: str | None = None) -> None:
        key = os.getenv("COHERE_API_KEY")
        if not key:
            raise RuntimeError("COHERE_API_KEY environment variable not set.")
        self._co = cohere.Client(key)
        self._embed_model = embed_model
        self._rerank_model = rerank_model or "rerank-english-v3.0"

    # ------------------------------------------------------------------
    #  Generic tree helpers
    # ------------------------------------------------------------------

    def discover_fields(self, data: Any, prefix: str = "") -> Set[str]:
        """Return every dot‑separated path in *data*."""
        fields: Set[str] = set()
        if isinstance(data, dict):
            for k, v in data.items():
                path = f"{prefix}.{k}" if prefix else k
                fields.add(path)
                fields.update(self.discover_fields(v, path))
        elif isinstance(data, list) and data and isinstance(data[0], (dict, list)):
            # Assume homogeneous list – inspect only first element for paths.
            fields.update(self.discover_fields(data[0], prefix))
        return fields

    def extract_value(self, data: Dict[str, Any], path: str) -> Any:
        current = data
        for key in path.split('.'):
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return None
        return current

    # ------------------------------------------------------------------
    #  Embedding & similarity search
    # ------------------------------------------------------------------

    @functools.lru_cache(maxsize=512)
    def _embed_batch(self, texts: Tuple[str, ...]) -> np.ndarray:
        """Embed *texts* using Cohere and return numpy (n × d) array."""
        response = self._co.embed(
            texts=list(texts), 
            model=self._embed_model, 
            input_type="search_document"
        )
        return np.array(response.embeddings, dtype=np.float32)

    def _top_k_matches(self, question: str, field_paths: List[str], k: int = 12, threshold: float = 0.25) -> List[Tuple[str, float]]:
        """Return best‑matching *field_paths* for *question* (path, score)."""
        if not field_paths:
            return []

        # Embed question and fields.
        q_vec = self._embed_batch((question,))[0]  # (d,)
        f_vecs = self._embed_batch(tuple(field_paths))  # (n × d)

        # Cosine similarities.
        sims = cosine_similarity_matrix(q_vec.reshape(1, -1), f_vecs).flatten()
        ranked = sorted([(p, s) for p, s in zip(field_paths, sims) if s >= threshold], key=lambda x: x[1], reverse=True)
        return ranked[:k]

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------

    def extract_relevant_data(self, telemetry: Dict[str, Any], question: str, *, top_k: int = 10, threshold: float = 0.25, rerank: bool = False) -> Dict[str, Any]:
        """Return nested dict of the *top‑k* fields most relevant to *question*."""
        # Build list of "section.path" strings spanning entire telemetry tree.
        field_paths = list(self.discover_fields(telemetry))
        top_fields = self._top_k_matches(question, field_paths, k=top_k * 3, threshold=threshold)  # grab a wider net first

        if rerank and top_fields:
            # Cohere Rerank API – better but slower.
            docs = [p for p, _ in top_fields]
            rr = self._co.rerank(model=self._rerank_model, query=question, documents=docs, top_n=min(top_k, len(docs)))
            reranked = [(docs[r.index], r.relevance_score) for r in rr.results]
        else:
            reranked = top_fields[:top_k]

        # Construct nested structure preserving original hierarchy.
        selected: Dict[str, Any] = {}
        for path, _score in reranked:
            value = self.extract_value(telemetry, path)
            if value is None:
                continue
            current = selected
            parts = path.split('.')
            for part in parts[:-1]:
                current = current.setdefault(part, {})  # type: ignore[assignment]
            current[parts[-1]] = value
        return selected

    # ------------------------------------------------------------------
    #  Nice printable summary
    # ------------------------------------------------------------------

    def summarize(self, extracted: Dict[str, Any]) -> str:
        if not extracted:
            return "No relevant telemetry data found."
        lines: List[str] = []
        self._summarize_recursive(extracted, lines, level=0)
        return "\n".join(lines)

    def _summarize_recursive(self, obj: Any, lines: List[str], level: int) -> None:
        indent = "  " * level
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, dict):
                    lines.append(f"{indent}{k}:")
                    self._summarize_recursive(v, lines, level + 1)
                else:
                    lines.append(f"{indent}- {k}: {self._format_value(v)}")
        else:
            lines.append(f"{indent}{self._format_value(obj)}")

    def _format_value(self, v: Any) -> str:
        if isinstance(v, float):
            return f"{v:.2f}"
        if isinstance(v, list):
            if v and isinstance(v[0], (list, tuple, dict)):
                return f"<{len(v)} records>"
            return f"[{', '.join(str(x) for x in v[:3])}{'...' if len(v) > 3 else ''}]"
        if isinstance(v, dict):
            return "{" + ", ".join(f"{k}: {self._format_value(vv)}" for k, vv in list(v.items())[:3]) + "}"
        return str(v)

    # ------------------------------------------------------------------
    #  Anomaly detection (unchanged from previous version)
    # ------------------------------------------------------------------

    # def highlight_anomalies(self, telemetry: Dict[str, Any]) -> List[Dict[str, Any]]:
    #     anomalies: List[Dict[str, Any]] = []

    #     def z_outliers(name: str, array: List[float], threshold: float = 2.5) -> None:
    #         if len(array) < 5:
    #             return
    #         arr = np.asarray(array, dtype=np.float32)
    #         z_scores = np.abs((arr - arr.mean()) / (arr.std() + 1e-6))
    #         for idx in np.where(z_scores > threshold)[0]:
    #             anomalies.append({
    #                 "feature": name,
    #                 "index": int(idx),
    #                 "value": float(arr[idx]),
    #                 "pattern": "z-score anomaly",
    #                 "hint": f"Unusual {name} value {arr[idx]:.2f} at index {idx}"
    #             })

    #     msgs = telemetry.get("messages", {})

    #     if "ATTITUDE" in msgs:
    #         for field in ("roll", "pitch", "yaw"):
    #             if field in msgs["ATTITUDE"]:
    #                 z_outliers(f"attitude.{field}", msgs["ATTITUDE"][field])

    #     if "GLOBAL_POSITION_INT" in msgs:
    #         for field in ("alt", "relative_alt", "vx", "vy", "vz"):
    #             if field in msgs["GLOBAL_POSITION_INT"]:
    #                 z_outliers(f"position.{field}", msgs["GLOBAL_POSITION_INT"][field])

    #     if "GPS_RAW_INT" in msgs and "satellites_visible" in msgs["GPS_RAW_INT"]:
    #         for idx, val in enumerate(msgs["GPS_RAW_INT"]["satellites_visible"]):
    #             if val < 6:
    #                 anomalies.append({
    #                     "feature": "gps.satellites_visible",
    #                     "index": idx,
    #                     "value": int(val),
    #                     "pattern": "low satellite count",
    #                     "hint": f"Only {val} satellites visible at index {idx}; GPS may be unreliable"
    #                 })

    #     return anomalies
