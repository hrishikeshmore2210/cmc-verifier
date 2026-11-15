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

import logging
import re
from typing import Callable, Optional

from ..config import get_settings
from ..models import Flag, Severity, VerificationState

log = logging.getLogger(__name__)

NUMERIC_TOLERANCE = 0.01  # default; override with CMC_NUMERIC_TOLERANCE (see config.py)


# ---- helpers ---------------------------------------------------------------

class SpecParseError(ValueError):
    """Raised when a specification string is not in a recognized format."""


_NUM = r"(\d+(?:\.\d+)?)"
_UNIT = r"\s*(?:%|[A-Za-z/%µ\.\s]*)?"
_RANGE_RE = re.compile(rf"^{_NUM}\s*(?:-|–|—|−|TO)\s*{_NUM}{_UNIT}$")
_UPPER_RE = re.compile(rf"^(?:NMT|<=|≤|<)\s*{_NUM}{_UNIT}$")
_LOWER_RE = re.compile(rf"^(?:NLT|>=|≥|>)\s*{_NUM}{_UNIT}$")


def parse_spec_limit(spec: str) -> tuple[Optional[float], Optional[float]]:
    """Return (low, high). None means unbounded on that side.

    Handles 'low-high' (hyphen/en dash/'to'), 'NMT x' / '<= x' (upper bound) and
    'NLT x' / '>= x' (lower bound), with optional trailing unit. Anything else
    raises SpecParseError: an unrecognized spec must never silently pass.
    """
    s = (spec or "").strip().upper()
    if m := _RANGE_RE.match(s):
        lo, hi = float(m.group(1)), float(m.group(2))
        if lo > hi:
            raise SpecParseError(f"inverted range in spec {spec!r}")
        return lo, hi
    if m := _UPPER_RE.match(s):
        return None, float(m.group(1))
    if m := _LOWER_RE.match(s):
        return float(m.group(1)), None
    raise SpecParseError(f"unrecognized specification format: {spec!r}")


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

def reconcile_measurement(claim, fact, tol=None):
    """Compare a dossier claim measurement to a source fact measurement.

    Returns None if they agree, else a human-readable mismatch reason. Handles
    three kinds of disagreement: value, qualifier ("<"/">"), and result type
    (numeric vs non-numeric like "ND").
    """
    if tol is None:
        tol = get_settings().numeric_tolerance
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
    log.info("check %s running", "numerical_reconciliation")
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


def _flag_source_masked_by_claim(flags, claim, result_fact, spec_fact, low, high, claim_verdict):
    """Independently evaluate the SOURCE result against the spec.

    If the source value violates the spec but the dossier claim does not, the claim
    is hiding an out-of-spec result. (When the claim also violates, the claim-level
    flag already covers it.)
    """
    if result_fact is None or claim_verdict == "violation":
        return
    if result_fact.result is None and result_fact.result_text is None:
        return
    src_verdict = evaluate_against_spec(
        result_fact.result, result_fact.qualifier, result_fact.result_text, low, high)
    if src_verdict != "violation":
        return
    reported = result_fact.result_text or f"{result_fact.qualifier or ''}{result_fact.result}{result_fact.unit or ''}"
    flags.append(Flag(
        check_name="spec_vs_result",
        severity=Severity.CRITICAL,
        message=(f"{claim.analyte} ({claim.batch_id}): source result {reported} violates "
                 f"specification '{spec_fact.spec_limit}' (dossier claim does not reflect this)"),
        dossier_ref=claim.ctd_section,
        source_ref=result_fact.source_ref,
        confidence=0.95,
        rationale="Source of record is out of specification; the dossier claim masks it.",
    ))


def check_spec_vs_result(state: VerificationState) -> VerificationState:
    log.info("check %s running", "spec_vs_result")
    flags: list[Flag] = []
    for link in state.get("links", []):
        c, sf = link["claim"], link["spec_fact"]
        if sf is None or sf.spec_limit is None:
            continue
        if c.quantitative_value is None and c.result_text is None:
            continue
        try:
            low, high = parse_spec_limit(sf.spec_limit)
        except SpecParseError as exc:
            flags.append(Flag(
                check_name="spec_vs_result",
                severity=Severity.MAJOR,
                message=f"{c.analyte} ({c.batch_id}): cannot evaluate specification ({exc})",
                dossier_ref=c.ctd_section,
                source_ref=sf.source_ref,
                confidence=0.9,
                rationale="Specification could not be parsed; conformance is indeterminate.",
            ))
            continue
        verdict = evaluate_against_spec(c.quantitative_value, c.qualifier, c.result_text, low, high)
        _flag_source_masked_by_claim(flags, c, link["result_fact"], sf, low, high, verdict)
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
    log.info("check %s running", "traceability")
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
    log.info("check %s running", "cross_section_consistency")
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


def _norm_unit(u):
    return None if u is None else u.strip().lower().replace(" ", "").replace("%w/w", "%").replace("%w/v", "%")


def check_unit_nomenclature(state: VerificationState) -> VerificationState:
    """Unit agreement between a result and its spec, and controlled-vocabulary analyte names."""
    log.info("check %s running", "unit_nomenclature")
    from ..adapters import canonical_analyte
    flags: list[Flag] = []
    for link in state.get("links", []):
        c, rf, sf = link["claim"], link["result_fact"], link["spec_fact"]
        if c.analyte and canonical_analyte(c.analyte) != c.analyte.strip():
            flags.append(Flag(
                check_name="unit_nomenclature",
                severity=Severity.MINOR,
                message=f"Non-standard analyte name '{c.analyte}' (standard: '{canonical_analyte(c.analyte)}')",
                dossier_ref=c.ctd_section,
                confidence=0.8,
                rationale="Dossier analyte name differs from the controlled vocabulary.",
            ))
        if rf and sf and rf.unit and sf.unit and _norm_unit(rf.unit) != _norm_unit(sf.unit):
            flags.append(Flag(
                check_name="unit_nomenclature",
                severity=Severity.MAJOR,
                message=f"{c.analyte} ({c.batch_id}): result unit '{rf.unit}' differs from specification unit '{sf.unit}'",
                dossier_ref=c.ctd_section,
                source_ref=rf.source_ref,
                confidence=0.9,
                rationale="Comparing values in different units is invalid without conversion.",
            ))
    return {"flags": flags}


# CTD sections a Module 3 drug-product quality summary is expected to cover.
REQUIRED_CTD_SECTIONS = ("3.2.P.5.1", "3.2.P.5.4")


def check_completeness_ctd(state: VerificationState) -> VerificationState:
    """Required sections present, and every batch with source results is reported."""
    log.info("check %s running", "completeness_ctd")
    flags: list[Flag] = []
    claims = state.get("claims", [])
    present = {c.ctd_section for c in claims}
    for section in REQUIRED_CTD_SECTIONS:
        if section not in present:
            flags.append(Flag(
                check_name="completeness_ctd",
                severity=Severity.MAJOR,
                message=f"Required CTD section {section} has no claims in the dossier",
                dossier_ref=section,
                confidence=0.9,
                rationale="A required section appears to be missing or empty.",
            ))
    import re as _re
    def key(b):
        return _re.sub(r"[^a-z0-9]", "", b.lower()) if b else None

    claimed = {key(c.batch_id) for c in claims}
    reported = set()
    for f in state.get("source_facts", []):
        k = key(f.batch_id)
        if f.result is None and f.result_text is None or k is None or k in claimed or k in reported:
            continue
        reported.add(k)
        flags.append(Flag(
            check_name="completeness_ctd",
            severity=Severity.MINOR,
            message=f"Batch {f.batch_id} has source results but no dossier claims",
            source_ref=f.source_ref,
            confidence=0.7,
            rationale="Source data exists for a batch the dossier does not report.",
        ))
    return {"flags": flags}


def _noop(check_name: str) -> Callable[[VerificationState], VerificationState]:
    def _check(state: VerificationState) -> VerificationState:
        log.info("check %s running (stub)", check_name)
        return {"flags": []}
    _check.__name__ = check_name
    return _check


# Registry -> the graph fans out over these keys.
CHECKS: dict[str, Callable[[VerificationState], VerificationState]] = {
    "numerical_reconciliation": check_numerical_reconciliation,
    "spec_vs_result": check_spec_vs_result,
    "traceability": check_traceability,
    "cross_section_consistency": check_cross_section_consistency,
    "unit_nomenclature": check_unit_nomenclature,
    "completeness_ctd": check_completeness_ctd,
    "stability_trend": _noop("stability_trend"),
}