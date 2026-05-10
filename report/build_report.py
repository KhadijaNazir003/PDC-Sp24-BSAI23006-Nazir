"""Builds report/PDC-A2-Report.pdf (Parts 1 + 2, <= 3 pages)."""
from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
)

OUT = Path(__file__).parent / "PDC-A2-Report.pdf"

styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=14, spaceAfter=4, spaceBefore=2, leading=16)
H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=11, spaceAfter=2, spaceBefore=4, leading=13)
BODY = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=9.5, leading=12, spaceAfter=4, alignment=4)
META = ParagraphStyle("Meta", parent=styles["BodyText"], fontSize=9, leading=11, textColor=HexColor("#555"))


class SequenceDiagram(Flowable):
    """UML sequence diagram for Part 2: optimistic-locking sync fix.

    Two concurrent users editing the same versioned doc. User A wins;
    User B's stale-version PUT is rejected with 409 and must merge+retry.
    """

    WIDTH = 6.6 * inch
    HEIGHT = 3.55 * inch

    def wrap(self, *_):
        return (self.WIDTH, self.HEIGHT)

    def draw(self):
        c = self.canv
        c.saveState()
        # 5 lifelines: A, B, API, DB, (notes column not a lifeline)
        lanes = [("User A", 0.55), ("User B", 1.85), ("FastAPI", 3.30), ("Database", 4.95)]
        top_y = self.HEIGHT - 0.30 * inch
        bot_y = 0.30 * inch

        # Header boxes + lifelines
        c.setFont("Helvetica-Bold", 9)
        for name, x_in in lanes:
            x = x_in * inch
            c.setFillColor(HexColor("#e8eef7"))
            c.setStrokeColor(black)
            c.rect(x - 0.55 * inch, top_y - 0.05 * inch, 1.10 * inch, 0.22 * inch, stroke=1, fill=1)
            c.setFillColor(black)
            c.drawCentredString(x, top_y + 0.02 * inch, name)
            # dashed lifeline
            c.setDash(2, 2)
            c.setStrokeColor(HexColor("#888"))
            c.line(x, top_y - 0.05 * inch, x, bot_y)
            c.setDash()

        # helper for arrows
        def arrow(x1, y, x2, label, dashed=False, color=black):
            c.setStrokeColor(color)
            c.setFillColor(color)
            if dashed:
                c.setDash(3, 2)
            c.line(x1, y, x2, y)
            c.setDash()
            # arrowhead
            head = 0.06 * inch
            direction = 1 if x2 > x1 else -1
            c.line(x2, y, x2 - direction * head, y + head / 2)
            c.line(x2, y, x2 - direction * head, y - head / 2)
            # label centered
            c.setFont("Helvetica", 7.8)
            c.setFillColor(black)
            c.drawString(min(x1, x2) + 0.05 * inch, y + 0.04 * inch, label)
            c.setStrokeColor(black)

        x_a = lanes[0][1] * inch
        x_b = lanes[1][1] * inch
        x_api = lanes[2][1] * inch
        x_db = lanes[3][1] * inch

        y = top_y - 0.40 * inch
        step = 0.24 * inch

        arrow(x_a, y, x_api, "GET /doc/42  ->  {body, version=7}");                  y -= step
        arrow(x_b, y, x_api, "GET /doc/42  ->  {body, version=7}");                  y -= step
        arrow(x_a, y, x_api, "PUT /doc/42  If-Match: 7  body=A'");                   y -= step
        arrow(x_api, y, x_db, "UPDATE ... WHERE id=42 AND version=7  SET version=8", color=HexColor("#0a5"));   y -= step
        arrow(x_db, y, x_api, "1 row updated", dashed=True, color=HexColor("#0a5"));  y -= step
        arrow(x_api, y, x_a, "200 OK  {version=8}", dashed=True, color=HexColor("#0a5")); y -= step
        arrow(x_b, y, x_api, "PUT /doc/42  If-Match: 7  body=B'");                   y -= step
        arrow(x_api, y, x_db, "UPDATE ... WHERE id=42 AND version=7", color=HexColor("#c33")); y -= step
        arrow(x_db, y, x_api, "0 rows updated  (version is now 8)", dashed=True, color=HexColor("#c33")); y -= step
        arrow(x_api, y, x_b, "409 Conflict  {server_version=8}", dashed=True, color=HexColor("#c33")); y -= step
        # B reconciles
        c.setFillColor(HexColor("#c33"))
        c.setFont("Helvetica-Oblique", 7.8)
        c.drawString(x_b - 0.55 * inch, y + 0.02 * inch, "User B: GET latest, merge B' on top of v8, PUT If-Match: 8")
        c.setFillColor(black)

        c.restoreState()


def stamp(canv, doc):
    canv.saveState()
    canv.setFont("Helvetica", 8)
    canv.setFillColor(HexColor("#777"))
    canv.drawString(0.6 * inch, 0.4 * inch, "Khadija Nazir  -  BSAI23006  -  PDC Assignment 2")
    canv.drawRightString(LETTER[0] - 0.6 * inch, 0.4 * inch, f"Page {doc.page}")
    canv.restoreState()


def build():
    doc = BaseDocTemplate(
        str(OUT),
        pagesize=LETTER,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        title="PDC Assignment 2 - Resilient Distributed Systems",
        author="Khadija Nazir (BSAI23006)",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=stamp)])

    flow = []

    flow.append(Paragraph("PDC Assignment 2 — Building Resilient Distributed Systems", H1))
    flow.append(Paragraph("Khadija Nazir &nbsp;·&nbsp; BSAI23006 &nbsp;·&nbsp; Spring 2026", META))
    flow.append(Spacer(1, 4))

    # ---------------- PART 1 ----------------
    flow.append(Paragraph("Part 1 — Root-cause analysis", H1))

    flow.append(Paragraph("1. Synchronization (Lost Update on shared docs).", H2))
    flow.append(Paragraph(
        "The naive PUT handler reads no version and runs <i>UPDATE docs SET body = :new WHERE id = :id</i>. "
        "Two clients that both pulled version 7 happily issue overlapping writes; the second commit silently "
        "stomps the first because nothing in the API lifecycle compares the row state at read-time to the "
        "row state at write-time. This is the textbook lost-update anomaly, and at SQL isolation level "
        "READ COMMITTED (the FastAPI/Postgres default) the database itself will not detect it — both "
        "transactions see a valid pre-image and the later writer simply overwrites. The bug lives in the "
        "<b>API layer</b> (no optimistic concurrency control), not in the database engine.",
        BODY))

    flow.append(Paragraph("2. Coordination (dropped Clerk webhook = permanent state drift).", H2))
    flow.append(Paragraph(
        "Clerk fires <i>subscription.cancelled</i> over HTTPS and treats a non-2xx (or a TCP reset) as the "
        "signal to retry. The current handler accepts the POST, flips <code>users.is_premium = false</code>, "
        "returns 200, and forgets it ever happened. Two failure modes leave us inconsistent forever: "
        "(a) the network drops the request before our process sees it and Clerk's retries have a finite "
        "ceiling; (b) we 200-ack the webhook but crash before committing the DB write. There is no idempotency "
        "key, no inbox table, and no reconciliation job — once the event is gone, the only source of truth "
        "(Clerk) and our copy (DB) diverge with no closed-loop mechanism to reconverge.",
        BODY))

    flow.append(Paragraph("3. Fault tolerance (synchronous LLM = single point of failure).", H2))
    flow.append(Paragraph(
        "FastAPI runs on a Uvicorn worker pool. <code>POST /summarize</code> calls the external LLM with a "
        "default <i>requests/httpx</i> client and no timeout, so when the upstream stalls, the handler "
        "<code>await</code>s for ~60 s before the OS-level TCP timeout fires. With one worker that is one "
        "blocked event loop; with four workers and a few hundred concurrent users, every worker ends up "
        "parked on a dead socket and the entire app appears down — to users hitting <i>any</i> route, not "
        "just the LLM-backed one. The failure of one external dependency cascades into a global outage "
        "because we have no per-call timeout, no budget, no circuit breaker, and no fallback.",
        BODY))

    # ---------------- PART 2 ----------------
    flow.append(Paragraph("Part 2 — Design", H1))

    flow.append(Paragraph("Sync fix — optimistic locking with row versioning.", H2))
    flow.append(Paragraph(
        "Add an integer <code>version</code> column to <code>docs</code>. GET returns it; PUT requires it via "
        "an <code>If-Match</code> header. The write becomes a conditional update: "
        "<code>UPDATE docs SET body=:b, version=version+1 WHERE id=:id AND version=:expected</code>. If the "
        "row count is 0, we return <b>409 Conflict</b> with the server's current version, and the client "
        "performs a three-way merge and retries. This is cheap (one integer, one extra WHERE clause), it "
        "scales horizontally because no shared lock is held across the request, and it converts a silent "
        "data-loss bug into a visible, recoverable error. The sequence diagram below traces two concurrent "
        "users; A wins, B is rejected and reconciles.",
        BODY))

    flow.append(SequenceDiagram())

    flow.append(Paragraph("Coordination fix — idempotent inbox + retry queue + DLQ.", H2))
    flow.append(Paragraph(
        "Clerk already sends a unique <code>svix-id</code> per delivery. The handler does the bare minimum "
        "synchronously: verify signature, INSERT the event row into a <code>webhook_inbox</code> table with a "
        "UNIQUE constraint on the Svix ID (so duplicate retries are no-ops), return 200. A separate worker "
        "(Celery / RQ / a simple background task) drains the inbox and applies the state change inside one "
        "DB transaction, marking the row processed. If the worker raises, we exponentially back off; after "
        "N attempts the row moves to a <i>dead-letter</i> table that pages on-call. This decouples webhook "
        "acknowledgement from business-logic success: a network blip costs us a Clerk retry (free), and a "
        "bug in our handler is visible and replayable instead of silently lost.",
        BODY))

    flow.append(Paragraph("Fault-tolerance fix — circuit breaker + bounded timeout + fallback.", H2))
    flow.append(Paragraph(
        "Wrap every LLM call in a state machine with three states: CLOSED (normal), OPEN (rejecting), "
        "HALF_OPEN (probing). Each call has a hard <code>asyncio.wait_for</code> timeout (2 s in this "
        "implementation), so no request can ever block the worker for 60 s. Three consecutive failures (or "
        "timeouts) flip the breaker to OPEN; subsequent calls return immediately with a fallback summary "
        "(first 200 chars of the input plus a banner) instead of even attempting the upstream. After a "
        "10-second cooldown the breaker enters HALF_OPEN and lets one trial through; success closes it, "
        "failure re-opens it. The upshot: the LLM going down degrades the feature, not the app. "
        "Implementation lives in <code>app/circuit_breaker.py</code>; the failure-triggering test "
        "<code>test_breaker_opens_after_threshold_when_llm_hangs</code> proves the fix.",
        BODY))

    flow.append(Paragraph("CAP / PACELC trade-offs.", H2))
    flow.append(Paragraph(
        "Per problem: <b>Sync (CP-leaning).</b> Optimistic locking refuses the late writer rather than "
        "merging blindly — we choose Consistency over Availability for the conflicting request, paying "
        "with a one-round-trip retry and a small latency hit on conflicts. <b>Coordination (eventually "
        "consistent / AP).</b> The inbox+worker design accepts a brief window where Clerk knows the user "
        "cancelled and we don't, in exchange for Availability under network partitions: webhooks are never "
        "dropped, just delayed. Idempotency keys make the eventual reconvergence safe. <b>Fault tolerance "
        "(AP, with degraded C).</b> The breaker chooses Availability of <i>the app</i> over Consistency of "
        "<i>the LLM feature</i>: when the upstream is down, users see a fallback summary rather than a "
        "30-second hang or a 502. PACELC: Else (no partition), we still pay a Latency cost — every call "
        "now has timeout overhead and a small lock acquisition — which is the price of bounding the "
        "worst case.",
        BODY))

    doc.build(flow)
    print(f"wrote {OUT}  ({OUT.stat().st_size/1024:.1f} KB)")


if __name__ == "__main__":
    build()
