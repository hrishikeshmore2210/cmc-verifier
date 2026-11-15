"""Retrieval / grounding (ARCHITECTURE.md §2.4).

PHASE 0 version: deterministic key match on (analyte, batch_id) for result facts
and (analyte) for spec facts. Real hybrid retrieval (structured + semantic) slots
in here later; the link contract stays the same.

Keys are normalized (analyte aliases, case/whitespace, batch punctuation) so
"Water" matches "Water Content" and "B-001" matches "b001". Conflicting duplicate
source facts for one key are surfaced as flags instead of silently first-wins.

Each link = {"claim": Claim, "result_fact": SourceFact|None, "spec_fact": SourceFact|None}
"""

from __future__ import annotations

import re

from ..adapters import canonical_analyte
from ..models import Flag, Severity, VerificationState


def _akey(analyte):
    if analyte is None:
        return None
    return re.sub(r"\s+", " ", canonical_analyte(analyte)).strip().lower()


def _bkey(batch):
    if batch is None:
        return None
    return re.sub(r"[^a-z0-9]", "", batch.lower())


def _signature(f):
    return (f.result, f.qualifier, f.result_text)


def ground(state: VerificationState) -> VerificationState:
    claims = state.get("claims", [])
    facts = state.get("source_facts", [])
    result_facts = [f for f in facts if f.result is not None or f.result_text is not None]
    spec_facts = [f for f in facts if f.spec_limit is not None]

    flags: list[Flag] = []
    reported_conflicts: set = set()

    def matches(c):
        if c.analyte is None:           # never match None == None
            return [], []
        ak, bk = _akey(c.analyte), _bkey(c.batch_id)
        rfs = [f for f in result_facts
               if _akey(f.analyte) == ak and bk is not None and _bkey(f.batch_id) == bk]
        sfs = [f for f in spec_facts if _akey(f.analyte) == ak]
        return rfs, sfs

    links = []
    for c in claims:
        rfs, sfs = matches(c)
        rf = rfs[0] if rfs else None
        sf = sfs[0] if sfs else None

        key = (_akey(c.analyte), _bkey(c.batch_id))
        if len({_signature(f) for f in rfs}) > 1 and key not in reported_conflicts:
            reported_conflicts.add(key)
            vals = "; ".join(f"{f.qualifier or ''}{f.result if f.result is not None else f.result_text} "
                             f"[{f.source_ref.document_id}]" for f in rfs)
            flags.append(Flag(
                check_name="grounding",
                severity=Severity.MAJOR,
                message=f"{c.analyte} ({c.batch_id}): conflicting source results: {vals}",
                dossier_ref=c.ctd_section,
                source_ref=rf.source_ref,
                confidence=0.9,
                rationale="Multiple source documents disagree; the source of record is ambiguous.",
            ))
        if len({f.spec_limit for f in sfs}) > 1 and (key[0], "spec") not in reported_conflicts:
            reported_conflicts.add((key[0], "spec"))
            flags.append(Flag(
                check_name="grounding",
                severity=Severity.MAJOR,
                message=f"{c.analyte}: conflicting specifications: "
                        + "; ".join(sorted({f.spec_limit for f in sfs})),
                dossier_ref=c.ctd_section,
                source_ref=sf.source_ref,
                confidence=0.9,
                rationale="Multiple specification limits found for one analyte.",
            ))
        links.append({"claim": c, "result_fact": rf, "spec_fact": sf})

    grounded = sum(1 for l in links if l["result_fact"] is not None)
    print(f"[ground] linked {grounded}/{len(links)} claim(s) to a source result")
    return {"links": links, "flags": flags}
