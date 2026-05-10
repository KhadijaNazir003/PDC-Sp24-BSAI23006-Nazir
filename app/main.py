"""StudySync — minimal FastAPI mock

Implements the Circuit Breaker fix for Fault Tolerance.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .circuit_breaker import CircuitBreaker, CircuitOpenError
from .llm_client import LLMMode, llm

STUDENT_ID = "BSAI23006"

app = FastAPI(title="StudySync (PDC A2)")

# Tight thresholds so the demo finishes inside 2 minutes.
breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0, call_timeout=2.0)


@app.middleware("http")
async def add_student_id_header(request: Request, call_next):
    """Stamps X-Student-ID on EVERY response, including errors. Required by spec."""
    try:
        response = await call_next(request)
    except Exception:
        response = JSONResponse({"detail": "internal error"}, status_code=500)
    response.headers["X-Student-ID"] = STUDENT_ID
    return response


class SummarizeIn(BaseModel):
    text: str


class SummarizeOut(BaseModel):
    summary: str
    source: str  # "llm" or "fallback"
    breaker_state: str


def _fallback_summary(text: str) -> str:
    snippet = text.strip().replace("\n", " ")[:200]
    return f"[fallback — LLM unavailable] {snippet}{'...' if len(text) > 200 else ''}"


@app.post("/summarize", response_model=SummarizeOut)
async def summarize(payload: SummarizeIn) -> SummarizeOut:
    try:
        summary = await breaker.call(llm.summarize, payload.text)
        return SummarizeOut(summary=summary, source="llm", breaker_state=breaker.state.value)
    except CircuitOpenError:
        return SummarizeOut(
            summary=_fallback_summary(payload.text),
            source="fallback",
            breaker_state=breaker.state.value,
        )
    except Exception:
        # Timeout or upstream error: fail fast with a fallback so the request
        # thread never hangs for 60 seconds.
        return SummarizeOut(
            summary=_fallback_summary(payload.text),
            source="fallback",
            breaker_state=breaker.state.value,
        )


@app.get("/health")
async def health():
    return {"status": "ok", "breaker": breaker.snapshot(), "llm_mode": llm.mode.value}


# demo controls 
class ModeIn(BaseModel):
    mode: LLMMode


@app.post("/admin/llm-mode")
async def set_llm_mode(body: ModeIn):
    """Flip the mock LLM between healthy / hang / error. Demo-only."""
    llm.set_mode(body.mode)
    return {"llm_mode": llm.mode.value}
