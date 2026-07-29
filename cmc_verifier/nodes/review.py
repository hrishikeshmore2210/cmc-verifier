"""Human-in-the-loop review (ARCHITECTURE.md §4).

In production this is a real interrupt: the human accepts / dismisses / requests
info on each flag, and every action writes an immutable decision event (§5 audit
trail). To make that real in LangGraph, compile the graph with a checkpointer and
`interrupt_before=["human_review"]` (see graph.py), then resume after the human
acts.

For now: a stub that finalizes the report so the pipeline runs to completion.
"""

from __future__ import annotations

from ..models import VerificationState


def human_review(state: VerificationState) -> VerificationState:
    report = dict(state.get("report", {}))
    report["status"] = "awaiting_human_review"
    n = report.get("total_flags", 0)
    print(f"[human_review] {n} flag(s) queued for a human to adjudicate")
    return {"report": report}
