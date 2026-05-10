"""Async circuit breaker: CLOSED -> OPEN -> HALF_OPEN -> CLOSED.

Wraps a coroutine. After `failure_threshold` consecutive failures (or one
timeout exceeding `call_timeout`), the breaker opens and rejects calls
immediately for `recovery_timeout` seconds. The next call after that
window enters HALF_OPEN: one trial call decides whether to close again
or stay open.
"""
from __future__ import annotations

import asyncio
import time
from enum import Enum
from typing import Any, Awaitable, Callable


class State(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when a call is rejected because the breaker is OPEN."""


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 10.0,
        call_timeout: float = 2.0,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.call_timeout = call_timeout

        self._state: State = State.CLOSED
        self._failures: int = 0
        self._opened_at: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> State:
        return self._state

    def _should_attempt_reset(self) -> bool:
        return time.monotonic() - self._opened_at >= self.recovery_timeout

    async def call(self, func: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
        async with self._lock:
            if self._state is State.OPEN:
                if self._should_attempt_reset():
                    self._state = State.HALF_OPEN
                else:
                    raise CircuitOpenError("circuit is open")

        try:
            result = await asyncio.wait_for(func(*args, **kwargs), timeout=self.call_timeout)
        except (asyncio.TimeoutError, Exception) as exc:
            await self._on_failure()
            raise exc
        else:
            await self._on_success()
            return result

    async def _on_success(self) -> None:
        async with self._lock:
            self._failures = 0
            self._state = State.CLOSED

    async def _on_failure(self) -> None:
        async with self._lock:
            self._failures += 1
            if self._state is State.HALF_OPEN or self._failures >= self.failure_threshold:
                self._state = State.OPEN
                self._opened_at = time.monotonic()

    def snapshot(self) -> dict:
        return {
            "state": self._state.value,
            "failures": self._failures,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout_s": self.recovery_timeout,
            "call_timeout_s": self.call_timeout,
        }
