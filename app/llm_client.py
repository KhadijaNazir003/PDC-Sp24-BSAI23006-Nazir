"""Mock LLM client. Behavior is switchable at runtime so the demo can flip
between healthy / hanging / erroring without restarting the server."""
from __future__ import annotations

import asyncio
from enum import Enum


class LLMMode(str, Enum):
    HEALTHY = "healthy"
    HANG = "hang"
    ERROR = "error"


class MockLLM:
    def __init__(self, mode: LLMMode = LLMMode.HEALTHY):
        self.mode = mode

    def set_mode(self, mode: LLMMode) -> None:
        self.mode = mode

    async def summarize(self, text: str) -> str:
        if self.mode is LLMMode.HANG:
            # Simulates the real bug: external API hangs for ~60s.
            await asyncio.sleep(60)
            return "(would never get here)"
        if self.mode is LLMMode.ERROR:
            raise RuntimeError("upstream LLM 503")
        # HEALTHY
        await asyncio.sleep(0.05)
        words = text.split()
        return f"Summary ({len(words)} words): " + " ".join(words[:12]) + ("..." if len(words) > 12 else "")


llm = MockLLM()
