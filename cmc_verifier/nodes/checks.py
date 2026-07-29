"""The check agents (ARCHITECTURE.md §3).

Each check reads `links` and returns ONLY {"flags": [...]} (that key has an
operator.add reducer; the checks run in parallel). Deterministic-in-code where
possible: the arithmetic never touches an LLM.

Implemented in Phase 0 (the three highest-trust checks):
  - numerical_reconciliation
  - spec_vs_result
  - traceability
The remaining four are stubs until their turn in the roadmap.
"""

from __future__ import annotations

from typing import Callable, Optional

from ..models import Flag, Severity, VerificationState

NUMERIC_TOLERANCE = 0.01  # absolute; tighten/units-aware later


# ---- helpers ---------------------------------------------------------------

def parse_spec_limit(spec: str) -> tuple[Optional[float], Optional[float]]:
    """Return (low, high). None means unbounded on that side.
    Handles 'low-high', 'NMT x' (not more than), 'NLT x' (not less than)."""
    s = spec.strip().upper()
    if s.startswith("NMT"):
        return None, float(s.split()[1])
    if s.startswith("NLT"):
        return float(s.split()[1]), None
    if "-" in s:
        lo, hi = s.split("-", 1)
        return float(lo), float(hi)
    return None, None

def evaluate_against_spec(value, qualifier, result_text, low, high):
    """Verdict for a reported result vs a spec: 'pass' | 'violation' | 'indeterminate'.

    Handles limit results ('<', '<=', '>', '>=') and non-numeric results ('ND').
    A qualifier makes the true value only partially known, so some comparisons are
    'indeterminate' — we cannot confirm conformance, which is itself worth flagging.
    """
    if result_text is not None:
        if result_text.upper() == "ND":       # not detected ~ below detection (~0)
            return "violation" if low is not None else "pass"
        return "indeterminate"                # unknown qualitative token

    if value is None:
        return "indeterminate"

    if not qualifier:                         # plain numeric
        if (low is not None and value < low) or (high is not None and value > high):
            return "violation"
        return "pass"

    verdicts = []
    if qualifier in ("<", "<="):              # true value bounded ABOVE by `value`
        if high is not None:
            verdicts.append("pass" if value <= high else "indeterminate")
        if low is not None:
            verdicts.append("violation" if value <= low else "indeterminate")
    else:                                     # ">"/">=": bounded BELOW by `value`
        if low is not None:
            verdicts.append("pass" if value >= low else "indeterminate")
        if high is not None:
            verdicts.append("violation" if value >= high else "indeterminate")

    if "violation" in verdicts:
        return "violation"
    if "indeterminate" in verdicts:
        return "indeterminate"
    return "pass"

# ---- implemented checks ----------------------------------------------------

def reconcile_measurement(claim, fact, tol=NUMERIC_TOLERANCE):
    """Compare a dossier claim measurement to a source fact measurement.

    Returns None if they agree, else a human-readable mismatch reason. Handles
    three kinds of disagreement: value, qualifier ("<"/">"), and result type
    (numeric vs non-numeric like "ND").
    """
    unit = fact.unit or ""

    def fmt(value, qualifier, result_text):
        if result_text is not None:
            return result_text
        if value is None:
            return "(none)"
        return f"{qualifier or ''}{value}{unit}"

    cm = fmt(claim.quantitative_value, claim.qualifier, claim.result_text)
    sm = fmt(fact.result, fact.qualifier, fact.result_text)

    # Non-numeric on either side (e.g. "ND"): must match exactly.
    if claim.result_text is not None or fact.result_text is not None:
        if claim.result_text != fact.result_text:
            return f"result type mismatch: dossier states {cm}, source reports {sm}"
        return None

    # Both numeric.
    if claim.quantitative_value is None or fact.result is None:
        return None
    if abs(claim.quantitative_value - fact.result) > tol:
        return f"value mismatch: dossier states {cm}, source reports {sm}"
    if (claim.qualifier or None) != (fact.qualifier or None):
        return f"qualifier mismatch: dossier states {cm}, source reports {sm}"
    return None


def check_numerical_reconciliation(state: VerificationState) -> VerificationState:
    print("[check:numerical_reconciliation] running")
    flags: list[Flag] = []
    for link in state.get("links", []):
        c, rf = link["claim"], link["result_fact"]
        if rf is None:
            continue
        if c.quantitative_value is None and c.result_text is None:
            continue
        reason = reconcile_measurement(c, rf)
        if reason is None:
            continue
        flags.append(Flag(
            check_name="numerical_reconciliation",
            severity=Severity.MAJOR,
            message=f"{c.analyte} ({c.batch_id}): {reason}",
            dossier_ref=c.ctd_section,
            source_ref=rf.source_ref,
            confidence=0.95,
            rationale="Reported measurement does not match the source of record.",
        ))
    return {"flags": flags}


def check_spec_vs_result(state: VerificationState) -> VerificationState:
    print("[check:spec_vs_result] running")
    flags: list[Flag] = []
    for link in state.get("links", []):
        c, sf = link["claim"], link["spec_fact"]
        if sf is None or sf.spec_limit is None:
            continue
        if c.quantitative_value is None and c.result_text is None:
            continue
        low, high = parse_spec_limit(sf.spec_limit)
        verdict = evaluate_against_spec(c.quantitative_value, c.qualifier, c.result_text, low, high)
        if verdict == "pass":
            continue
        reported = c.result_text or f"{c.qualifier or ''}{c.quantitative_value}{sf.unit or ''}"
        if verdict == "violation":
            sev, note, conf = Severity.CRITICAL, "violates specification", 0.97
        else:  # indeterminate
            sev, note, conf = Severity.MAJOR, "cannot be confirmed within specification", 0.7
        flags.append(Flag(
            check_name="spec_vs_result",
            severity=sev,
            message=f"{c.analyte} ({c.batch_id}): reported {reported} {note} '{sf.spec_limit}'",
            dossier_ref=c.ctd_section,
            source_ref=sf.source_ref,
            confidence=conf,
            rationale=f"Spec-vs-result verdict: {verdict}.",
        ))
    return {"flags": flags}


def check_traceability(state: VerificationState) -> VerificationState:
    print("[check:traceability] running")
    flags: list[Flag] = []
    for link in state.get("links", []):
        c, rf = link["claim"], link["result_fact"]
        if c.quantitative_value is not None and rf is None:
            flags.append(Flag(
                check_name="traceability",
                severity=Severity.MAJOR,
                message=(f"{c.analyte} ({c.batch_id}): quantitative claim has no "
                         f"matching source record"),
                dossier_ref=c.ctd_section,
                source_ref=None,
                confidence=0.9,
                rationale="Ungrounded quantitative claim; no source to verify against.",
            ))
    return {"flags": flags}

def _measurement_str(c):
    if c.result_text is not None:
        return c.result_text
    if c.quantitative_value is None:
        return "(none)"
    return f"{c.qualifier or ''}{c.quantitative_value}"


def check_cross_section_consistency(state: VerificationState) -> VerificationState:
    print("[check:cross_section_consistency] running")
    flags: list[Flag] = []
    groups: dict = {}
    for c in state.get("claims", []):
        if c.analyte is None or c.batch_id is None:
            continue
        groups.setdefault((c.analyte, c.batch_id), []).append(c)
    for (analyte, batch), claims in groups.items():
        by_meas: dict = {}
        for c in claims:
            by_meas.setdefault(_measurement_str(c), set()).add(c.ctd_section)
        if len(by_meas) <= 1:
            continue                       # every mention agrees
        sections = set().union(*by_meas.values())
        if len(sections) < 2:
            continue                       # conflict sits inside one section, not across
        detail = "; ".join(f"{m} in {', '.join(sorted(secs))}"
                           for m, secs in sorted(by_meas.items()))
        flags.append(Flag(
            check_name="cross_section_consistency",
            severity=Severity.MAJOR,
            message=f"{analyte} ({batch}): stated inconsistently across sections — {detail}",
            dossier_ref=", ".join(sorted(sections)),
            source_ref=None,
            confidence=0.9,
            rationale="The same result appears with different values in different dossier sections.",
        ))
    return {"flags": flags}


# ---- not-yet-implemented checks -------------------------------------------

def _noop(check_name: str) -> Callable[[VerificationState], VerificationState]:
    def _check(state: VerificationState) -> VerificationState:
        print(f"[check:{check_name}] running (stub)")
        return {"flags": []}
    _check.__name__ = check_name
    return _check


# Registry -> the graph fans out over these keys.
CHECKS: dict[str, Callable[[VerificationState], VerificationState]] = {
    "numerical_reconciliation": check_numerical_reconciliation,
    "spec_vs_result": check_spec_vs_result,
    "traceability": check_traceability,
    "cross_section_consistency": check_cross_section_consistency,
    "unit_nomenclature": _noop("unit_nomenclature"),
    "completeness_ctd": _noop("completeness_ctd"),
    "stability_trend": _noop("stability_trend"),
}