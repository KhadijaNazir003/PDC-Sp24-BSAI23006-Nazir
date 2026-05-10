"""Demo helper: shows the BEFORE state for the video.

A naive synchronous-style call straight into the LLM with NO breaker. When
the LLM hangs, this script blocks for 60s. Run it to demonstrate the
problem before showing how the breaker fixes it. Ctrl+C to abort early.

Usage:
    python tests/demo_before_fix.py
"""
import asyncio
import time

from app.llm_client import LLMMode, MockLLM


async def main():
    llm = MockLLM(LLMMode.HANG)  # external API is down
    print("Calling LLM with NO circuit breaker (request will hang ~60s)...")
    t0 = time.monotonic()
    try:
        await asyncio.wait_for(llm.summarize("doc"), timeout=65)
    except asyncio.TimeoutError:
        pass
    print(f"...blocked for {time.monotonic() - t0:.1f}s. Whole server thread was unresponsive.")


if __name__ == "__main__":
    asyncio.run(main())
