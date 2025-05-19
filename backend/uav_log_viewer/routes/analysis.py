from __future__ import annotations
"""FastAPI router – /analysis endpoint
Standalone endpoint that lets a client submit telemetry JSON and receive
pre‑computed metrics + primitive anomaly flags (no LLM).
Useful for front‑end dashboards.
"""

from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from uav_log_viewer.analysis import DataExtractor, compute_metrics

router = APIRouter(prefix="/analysis", tags=["analysis"])


class AnalysisRequest(BaseModel):
    telemetry: Dict[str, Any]
    # optional user hint – which metric/time‑window they care about
    hint: Optional[str] = None


class AnalysisResponse(BaseModel):
    metrics: Dict[str, Any]
    extracted_sample: Dict[str, Any]


@router.post("/", response_model=AnalysisResponse)
async def analysis_endpoint(req: AnalysisRequest):
    if not req.telemetry:
        raise HTTPException(status_code=400, detail="Telemetry payload missing")

    extractor = DataExtractor()
    extracted = extractor.extract_relevant_data(req.telemetry, req.hint or "", top_k=25)
    metrics = compute_metrics(extracted)
    return AnalysisResponse(metrics=metrics, extracted_sample=extracted)
