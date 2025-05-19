from fastapi import APIRouter

from .chat import router as chat_router
from .analysis import router as analysis_router

router = APIRouter()
router.include_router(chat_router)
router.include_router(analysis_router)

__all__ = ["router"]
