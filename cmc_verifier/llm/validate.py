"""Provenance gate for LLM output.

The model is untrusted: every extracted claim must be traceable to the document text
or it is rejected (and surfaced as a flag, never silently dropped). Checks:

  1. evidence_quote appears verbatim (whitespace-normalised) in the document
  2. the numeric value, qualifier, and ND/result_text are all present in that quote
  3. analyte, batch_id, and ctd_section appear in the document (no invented keys)
"""

from __future__ import annotations

import re

from ..adapters import ANALYTE_ALIASES, canonical_analyte
from ..models import Claim
from .schema import ExtractedClaim

_NUM_RE = re.compile(r"\d+(?:\.\d+)?")
_WS_RE = re.compile(r"\s+")

# Phrases that look like someone talking to the model rather than reporting a result.
_INJECTION_PATTERNS = [
    r"ignore (?:all |any )?(?:the )?(?:previous|prior|above) (?:instructions|prompts?)",
    r"disregard (?:all |any )?(?:the )?(?:previous|prior|above)",
    r"you are now\b",
    r"new instructions?:",
    r"system prompt",
    r"as an ai\b",
    r"do not (?:flag|report) (?:this|any)",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)


def _norm(s: str) -> str:
    return _WS_RE.sub(" ", s).strip()


def _analyte_in_document(analyte: str, doc_lower: str) -> bool:
    """True if the analyte, or any known alias of the same canonical analyte, is in the document.

    A model may legitimately normalise 'Total related substances' to the canonical
    'Related Substances - Total'; `ground` resolves aliases the same way. An analyte
    with no textual support at all is still rejected.
    """
    if _norm(analyte).lower() in doc_lower:
        return True
    canon = canonical_analyte(analyte)
    variants = {k for k, v in ANALYTE_ALIASES.items() if v == canon} | {canon.lower()}
    return any(v in doc_lower for v in variants)


def find_injection_phrases(text: str) -> list[str]:
    return sorted({m.group(0).lower() for m in _INJECTION_RE.finditer(text)})


def _reject_reason(c: ExtractedClaim, doc_norm: str, doc_lower: str) -> str | None:
    quote = _norm(c.evidence_quote)
    if not quote:
        return "empty evidence_quote"
    if quote not in doc_norm:
        return "evidence_quote is not verbatim text from the document"

    if c.quantitative_value is not None:
        nums = [float(n) for n in _NUM_RE.findall(quote)]
        if not any(abs(n - c.quantitative_value) < 1e-9 for n in nums):
            return f"value {c.quantitative_value} does not appear in the evidence_quote"
    if c.qualifier:
        wanted = {"<": "<≤", "<=": "<≤", ">": ">≥", ">=": ">≥"}[c.qualifier]
        if not any(ch in quote for ch in wanted):
            return f"qualifier '{c.qualifier}' does not appear in the evidence_quote"
    if c.result_text:
        t = c.result_text.upper()
        q_up = quote.upper()
        if not (t in q_up or (t == "ND" and "NOT DETECTED" in q_up)):
            return f"result_text '{c.result_text}' does not appear in the evidence_quote"
    if c.quantitative_value is None and c.result_text is None and c.claim_type == "quantitative":
        return "quantitative claim carries neither a value nor a result_text"

    if c.analyte and not _analyte_in_document(c.analyte, doc_lower):
        return f"analyte '{c.analyte}' does not appear in the document"
    if c.batch_id and _norm(c.batch_id).lower() not in doc_lower:
        return f"batch_id '{c.batch_id}' does not appear in the document"
    if c.ctd_section.lower() != "unknown" and c.ctd_section not in doc_norm:
        return f"ctd_section '{c.ctd_section}' does not appear in the document"
    return None


def validate_claims(extracted: list[ExtractedClaim], document_text: str):
    """Return (accepted: list[Claim], rejected: list[tuple[ExtractedClaim, reason]])."""
    doc_norm = _norm(document_text)
    doc_lower = doc_norm.lower()
    accepted: list[Claim] = []
    rejected: list[tuple[ExtractedClaim, str]] = []
    seen: set = set()
    for c in extracted:
        reason = _reject_reason(c, doc_norm, doc_lower)
        if reason:
            rejected.append((c, reason))
            continue
        key = (_norm(c.evidence_quote), c.analyte, c.batch_id, c.quantitative_value, c.qualifier, c.result_text)
        if key in seen:           # same sentence extracted twice
            continue
        seen.add(key)
        accepted.append(Claim(
            text_span=_norm(c.evidence_quote),
            ctd_section=c.ctd_section,
            claim_type=c.claim_type,
            analyte=c.analyte,
            batch_id=c.batch_id,
            quantitative_value=c.quantitative_value,
            qualifier=c.qualifier,
            result_text=c.result_text,
        ))
    return accepted, rejected
