from __future__ import annotations
"""FastAPI router – /chat endpoint
Receives user question + optional telemetry JSON and returns LLM response.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from uav_log_viewer.chat import process_chat_request

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str
    telemetry: Optional[Dict[str, Any]] = None  # parsed JSON dict from the front‑end


class ChatResponse(BaseModel):
    answer: str
    suggested_questions: List[str] = []


@router.post("/", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    result = process_chat_request(req.question, req.telemetry)
    return ChatResponse(**result)
