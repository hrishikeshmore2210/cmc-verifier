"""Critic / adjudication (ARCHITECTURE.md §3.2).

Characterizes flags (severity, tally); never resolves them. Writes
`adjudicated_flags` and `report`. Must NOT write `flags` (add-reducer).

Phase 0: pass raw flags through, dedupe exact duplicates, tally by severity.
Later: false-positive suppression, confidence calibration, cross-check dedupe.
"""

from __future__ import annotations

import logging

from ..models import Severity, VerificationState

log = logging.getLogger(__name__)


def critic(state: VerificationState) -> VerificationState:
    raw = state.get("flags", [])

    seen, adjudicated = set(), []
    for f in raw:
        key = (f.check_name, f.dossier_ref, f.message)
        if key in seen:
            continue
        seen.add(key)
        adjudicated.append(f)

    log.info(f"adjudicating {len(raw)} raw flag(s) -> {len(adjudicated)} unique")
    report = {
        "total_flags": len(adjudicated),
        "by_severity": {
            "critical": sum(f.severity == Severity.CRITICAL for f in adjudicated),
            "major": sum(f.severity == Severity.MAJOR for f in adjudicated),
            "minor": sum(f.severity == Severity.MINOR for f in adjudicated),
        },
        "by_check": {},
    }
    for f in adjudicated:
        report["by_check"][f.check_name] = report["by_check"].get(f.check_name, 0) + 1

    return {"adjudicated_flags": adjudicated, "report": report}