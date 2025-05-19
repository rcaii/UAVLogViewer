"""
conversation.py  –  lightweight per-process conversation memory
Keeps a rolling history of turns so we can feed brief context back to LLM
for follow-up questions. All data lives only in RAM.
"""

from __future__ import annotations
from typing import List, Dict

_MAX_HISTORY = 15           # keep the last N turns


class ConversationState:
    def __init__(self) -> None:
        self.history: List[Dict[str, str]] = []   # [{role, content}]

    # ------------------------------------------------------------------ #
    # public helpers
    # ------------------------------------------------------------------ #

    def append(self, role: str, content: str) -> None:
        """Add a turn and trim to _MAX_HISTORY."""
        self.history.append({"role": role, "content": content})
        if len(self.history) > _MAX_HISTORY:
            del self.history[0]

    def tail(self, n: int = 3) -> List[Dict[str, str]]:
        """Return the last *n* turns (default 3)."""
        return self.history[-n:]


# global singleton (per FastAPI worker / interpreter)
conversation_state = ConversationState()
