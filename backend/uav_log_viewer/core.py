"""
FastAPI application entry-point for the UAV-Log-Viewer backend.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router as api_router

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="UAV Log Viewer API",
        version="0.1.0",
        description="Endpoints for telemetry analysis, anomaly reasoning, and chat-LLM",
    )

    # CORS (adjust origins as needed)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount all feature routers
    app.include_router(api_router)

    # Simple health-check
    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
