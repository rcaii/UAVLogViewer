"""
Package initialiser for uav_log_viewer.

Exposes:
• `api_router` – aggregated FastAPI router (from uav_log_viewer.routes)
• `__version__`
"""

from __future__ import annotations

from importlib.metadata import version, PackageNotFoundError

try:
    __version__: str = version("uav_log_viewer")
except PackageNotFoundError:
    __version__ = "0.0.0"

from .routes import router as api_router          # noqa: E402 (after metadata import)

__all__ = ["api_router", "__version__"]
