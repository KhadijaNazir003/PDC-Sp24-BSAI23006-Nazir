Khadija Nazir - BSAI23006

# PDC Assignment 2 — Resilient Distributed Systems

Minimal FastAPI mock of the StudySync stack from the assignment, with a
working **Circuit Breaker** fix for Problem 3 (Fault Tolerance: hanging LLM).
See `app/main.py:24` for the middleware.

## Layout

```
app/
  main.py             FastAPI app, middleware, /summarize endpoint
  circuit_breaker.py  CLOSED -> OPEN -> HALF_OPEN state machine
  llm_client.py       Mock LLM with switchable mode (healthy/hang/error)
tests/
  test_circuit_breaker.py   pytest suite proving the fix works
  demo_before_fix.py        BEFORE-state demo for the video
report/
  PDC-Asm2-Report.pdf   Parts 1 + 2 (analysis + design)
```

## Run it

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/docs for Swagger UI. Verify the header:

```powershell
curl.exe -i -X POST http://localhost:8000/summarize -H "Content-Type: application/json" -d '{\"text\":\"hello world\"}'
```

## Run the tests

```powershell
python -m pytest -v
```

All 6 tests should pass in under 10 seconds. Key tests:

- `test_breaker_opens_after_threshold_when_llm_hangs` — fires 3 requests
  while the LLM is configured to hang for 60 s. Asserts (a) each request
  returns within ~2 s thanks to the per-call timeout, (b) the breaker
  transitions to `OPEN`, and (c) subsequent requests fail fast with the
  fallback in under 0.5 s. **This is the failure-triggering test for Part 3.**
- `test_breaker_recovers_through_half_open` — proves the breaker self-heals
  once the upstream comes back.
- `test_student_id_header_on_every_response` — proves the X-Student-ID header
  is stamped on success, validation-error (422), and other responses.

## Demo

The `before` state (server hangs ~60 s on a single bad call):

```powershell
python tests/demo_before_fix.py
```

The `after` state (server, with the breaker, stays responsive):

```powershell
# terminal 1
python -m uvicorn app.main:app --port 8000
# terminal 2 — flip the mock LLM to "hang", fire 5 requests, observe fast fallbacks
curl.exe -X POST http://localhost:8000/admin/llm-mode -H "Content-Type: application/json" -d '{\"mode\":\"hang\"}'
for ($i=0; $i -lt 5; $i++) { Measure-Command { curl.exe -s -X POST http://localhost:8000/summarize -H "Content-Type: application/json" -d '{\"text\":\"doc\"}' } | Select-Object TotalSeconds }
curl.exe http://localhost:8000/health
```
and subsequent calls return in milliseconds with `"breaker_state": "open"`.

## What's implemented for Part 3

Of the three bugs, this submission implements **the Circuit Breaker fix for
Problem 3 (Fault Tolerance)**. The other two are designed in the report PDF
but not coded — per assignment instructions ("write code for ONE of the
problems").
