"""Human-in-the-loop review (ARCHITECTURE.md §4).

With `build_graph(interactive=True)` the graph pauses BEFORE this node. The host
records the reviewer's decisions into state and resumes:

    app = build_graph(interactive=True)
    cfg = {"configurable": {"thread_id": run_id}}
    app.invoke(initial_state, cfg)                       # runs to the pause
    app.update_state(cfg, {"decisions": [make_decision(flag, Decision.ACCEPT, "alice")]})
    final = app.invoke(None, cfg)                        # resumes -> this node

Every decision is also written to the audit ledger by the caller
(`AuditLog.decision_recorded`). The system never resolves a flag itself.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from enum import Enum

from ..models import Flag, VerificationState

log = logging.getLogger(__name__)


class Decision(str, Enum):
    ACCEPT = "accept"            # discrepancy is real; dossier must be corrected
    DISMISS = "dismiss"          # false positive / not a discrepancy
    NEEDS_INFO = "needs_info"    # cannot decide yet


def flag_id(flag: Flag) -> str:
    """Stable short identity for a flag, so decisions survive re-runs."""
    ref = flag.source_ref
    key = "|".join([flag.check_name, flag.dossier_ref or "", flag.message,
                    "" if ref is None else f"{ref.document_id}:{ref.page}:{ref.location}"])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def make_decision(flag: Flag, decision: Decision, reviewer: str, note: str = "") -> dict:
    if not reviewer.strip():
        raise ValueError("a reviewer identity is required for every decision")
    return {
        "flag_id": flag_id(flag),
        "decision": Decision(decision).value,
        "reviewer": reviewer.strip(),
        "note": note,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def human_review(state: VerificationState) -> VerificationState:
    report = dict(state.get("report", {}))
    flags = state.get("adjudicated_flags", [])
    decided = {d["flag_id"]: d for d in state.get("decisions", [])}
    undecided = [f for f in flags if flag_id(f) not in decided]

    counts = {d.value: 0 for d in Decision}
    for d in decided.values():
        counts[d["decision"]] += 1
    report["decisions"] = counts
    report["status"] = "awaiting_human_review" if undecided else "reviewed"
    log.info("%d flag(s) total, %d undecided -> %s", len(flags), len(undecided), report["status"])
    return {"report": report}
