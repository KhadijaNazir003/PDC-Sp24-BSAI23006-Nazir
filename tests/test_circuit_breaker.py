"""Proves the Circuit Breaker fix handles the LLM-hang failure mode.

Failure scenario (no breaker): request thread blocks ~60s waiting on the
mock LLM and the entire app hangs. With the breaker:
  1. The first few hangs are cut off at `call_timeout` (2s in tests).
  2. After `failure_threshold` (3) failures, the breaker OPENS and rejects
     calls instantly with a fallback response.
  3. Once the upstream recovers and `recovery_timeout` elapses, the breaker
     transitions HALF_OPEN -> CLOSED on a successful trial call.
"""
from __future__ import annotations

import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from app.circuit_breaker import CircuitBreaker, CircuitOpenError, State
from app.llm_client import MockLLM, LLMMode
from app.main import app, breaker, llm


@pytest.fixture(autouse=True)
def _reset_state():
    """Each test starts CLOSED with a healthy LLM."""
    breaker._state = State.CLOSED
    breaker._failures = 0
    breaker._opened_at = 0.0
    llm.set_mode(LLMMode.HEALTHY)
    yield
    llm.set_mode(LLMMode.HEALTHY)


def test_student_id_header_on_every_response():
    """Spec rule: X-Student-ID must be on EVERY response."""
    with TestClient(app) as client:
        assert client.get("/health").headers.get("X-Student-ID") == "BSAI23006"
        r = client.post("/summarize", json={"text": "hello world"})
        assert r.headers.get("X-Student-ID") == "BSAI23006"
        # Even 422 validation errors must carry the header.
        r = client.post("/summarize", json={"wrong_field": 1})
        assert r.status_code == 422
        assert r.headers.get("X-Student-ID") == "BSAI23006"


def test_happy_path_uses_llm():
    with TestClient(app) as client:
        r = client.post("/summarize", json={"text": "the quick brown fox jumps over the lazy dog"})
        assert r.status_code == 200
        body = r.json()
        assert body["source"] == "llm"
        assert body["breaker_state"] == "closed"
        assert "Summary" in body["summary"]


def test_breaker_opens_after_threshold_when_llm_hangs():
    """When the LLM hangs, requests must NOT block 60s. The breaker should
    trip after 3 timeouts and serve fallback responses immediately."""
    with TestClient(app) as client:
        client.post("/admin/llm-mode", json={"mode": "hang"})

        # First 3 calls each hit the per-call timeout (~2s) and return fallback.
        start = time.monotonic()
        for _ in range(3):
            r = client.post("/summarize", json={"text": "doc"})
            assert r.status_code == 200
            assert r.json()["source"] == "fallback"
        warmup = time.monotonic() - start
        # Sanity: 3 timeouts of 2s each is ~6s. Far less than the 60s real hang.
        assert warmup < 10, f"breaker did not enforce timeout, took {warmup:.1f}s"

        # Breaker should now be OPEN. Subsequent calls return fallback INSTANTLY.
        h = client.get("/health").json()
        assert h["breaker"]["state"] == "open"

        t0 = time.monotonic()
        r = client.post("/summarize", json={"text": "another doc"})
        elapsed = time.monotonic() - t0
        assert r.status_code == 200
        assert r.json()["source"] == "fallback"
        assert elapsed < 0.5, f"open breaker should fail fast, took {elapsed:.3f}s"


def test_breaker_opens_on_repeated_errors():
    with TestClient(app) as client:
        client.post("/admin/llm-mode", json={"mode": "error"})
        for _ in range(3):
            r = client.post("/summarize", json={"text": "x"})
            assert r.json()["source"] == "fallback"
        assert client.get("/health").json()["breaker"]["state"] == "open"


@pytest.mark.asyncio
async def test_breaker_recovers_through_half_open():
    """After recovery_timeout, the breaker enters HALF_OPEN and one
    successful call closes it again."""
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.2, call_timeout=0.5)
    bad_llm = MockLLM(LLMMode.ERROR)
    good_llm = MockLLM(LLMMode.HEALTHY)

    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.call(bad_llm.summarize, "text")
    assert cb.state is State.OPEN

    # Within recovery window: still rejected.
    with pytest.raises(CircuitOpenError):
        await cb.call(good_llm.summarize, "text")

    await asyncio.sleep(0.25)

    # Trial call after recovery_timeout transitions HALF_OPEN -> CLOSED.
    result = await cb.call(good_llm.summarize, "text")
    assert "Summary" in result
    assert cb.state is State.CLOSED


@pytest.mark.asyncio
async def test_breaker_reopens_if_half_open_trial_fails():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.2, call_timeout=0.5)
    bad_llm = MockLLM(LLMMode.ERROR)

    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.call(bad_llm.summarize, "text")
    assert cb.state is State.OPEN

    await asyncio.sleep(0.25)
    with pytest.raises(RuntimeError):
        await cb.call(bad_llm.summarize, "text")  # half-open trial fails
    assert cb.state is State.OPEN
