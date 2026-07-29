"""Retrieval / grounding (ARCHITECTURE.md §2.4).

PHASE 0 version: deterministic key match on (analyte, batch_id) for result facts
and (analyte) for spec facts. Real hybrid retrieval (structured + semantic) slots
in here later; the link contract stays the same.

Each link = {"claim": Claim, "result_fact": SourceFact|None, "spec_fact": SourceFact|None}
"""

from __future__ import annotations

from ..models import VerificationState


def ground(state: VerificationState) -> VerificationState:
    claims = state.get("claims", [])
    facts = state.get("source_facts", [])
    result_facts = [f for f in facts if f.result is not None]
    spec_facts = [f for f in facts if f.spec_limit is not None]

    links = []
    for c in claims:
        rf = next((f for f in result_facts
                   if f.analyte == c.analyte and f.batch_id == c.batch_id), None)
        sf = next((f for f in spec_facts if f.analyte == c.analyte), None)
        links.append({"claim": c, "result_fact": rf, "spec_fact": sf})

    grounded = sum(1 for l in links if l["result_fact"] is not None)
    print(f"[ground] linked {grounded}/{len(links)} claim(s) to a source result")
    return {"links": links}