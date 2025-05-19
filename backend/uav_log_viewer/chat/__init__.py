"""uav_log_viewer.chat package

Exposes the chat‑layer utilities used by FastAPI routes.
"""

from .processor import process_chat_request
from .prompt import (
    build_metric_prompt,
    build_general_prompt,
    extract_response_parts,
)
from .conversation import conversation_state, ConversationState

__all__ = [
    "process_chat_request",
    "build_metric_prompt",
    "build_general_prompt",
    "extract_response_parts",
    "ConversationState",
    "conversation_state",
]
