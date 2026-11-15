"""Claim extraction from the dossier (ARCHITECTURE.md §2.3).

Routes by file type; the output contract (list[Claim]) is identical either way:

  *.json        structured claim records, parsed deterministically (no LLM, no API key)
  *.txt / *.md  a Module 3 narrative, extracted by an LLM (cmc_verifier.llm) and then
                gated by a verbatim-quote provenance check. Claims the model could not
                back with exact text become flags, never silent drops.

A failed LLM extraction yields NO claims plus a MAJOR flag, so a broken extraction can
never look like a clean dossier.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from ..config import get_settings
from ..models import Claim, Flag, Severity, VerificationState

log = logging.getLogger(__name__)

NARRATIVE_SUFFIXES = {".txt", ".md"}

# Injectable for tests / alternative providers: () -> LLMClaimExtractor
_extractor_factory = None


def set_extractor_factory(factory) -> None:
    global _extractor_factory
    _extractor_factory = factory


def _default_extractor():
    from ..llm.extractor import LLMClaimExtractor
    s = get_settings()
    return LLMClaimExtractor(model=s.llm_model, effort=s.llm_effort, cache_dir=s.llm_cache_dir)


def _flag(message: str, severity: Severity, rationale: str, ref: str | None = None) -> Flag:
    return Flag(check_name="extract_claims", severity=severity, message=message,
                dossier_ref=ref, confidence=1.0, rationale=rationale)


def _extract_structured(path: Path) -> VerificationState:
    rows = json.loads(path.read_text(encoding="utf-8-sig"))
    claims = [Claim(**row) for row in rows]
    log.info("parsed %d claim(s) from %s", len(claims), path)
    return {"claims": claims, "extraction_meta": {"method": "structured_json"}}


def _extract_narrative(path: Path) -> VerificationState:
    from ..llm.extractor import ExtractionError

    text = path.read_text(encoding="utf-8-sig")
    try:
        extractor = (_extractor_factory or _default_extractor)()
        outcome = extractor.extract(text)
    except ExtractionError as exc:
        log.error("LLM extraction failed: %s", exc)
        return {"claims": [], "extraction_meta": {"method": "llm", "error": str(exc)}, "flags": [_flag(
            f"LLM claim extraction failed for '{path.name}': {exc}", Severity.MAJOR,
            "No claims were extracted; the dossier was NOT verified. Do not treat as clean.")]}

    flags = []
    for claim, reason in outcome.rejected:
        flags.append(_flag(
            f"Extracted claim rejected ({reason}): \"{claim.evidence_quote[:120]}\"", Severity.MINOR,
            "The model proposed a claim it could not ground in the document text; a human should check "
            "whether a real claim was missed.", ref=claim.ctd_section))
    if outcome.injection_phrases:
        flags.append(_flag(
            f"Dossier text contains instruction-like phrases aimed at an AI reader: "
            f"{', '.join(outcome.injection_phrases)}", Severity.MAJOR,
            "Possible prompt-injection attempt. Extraction output was still provenance-checked, but review "
            "the document."))
    if not outcome.claims:
        flags.append(_flag(f"No claims could be extracted from '{path.name}'", Severity.MAJOR,
                           "An empty extraction must not be mistaken for a clean dossier."))
    log.info("LLM extraction: %d accepted, %d rejected", len(outcome.claims), len(outcome.rejected))
    return {"claims": outcome.claims, "extraction_meta": outcome.meta, "flags": flags}


def extract_claims(state: VerificationState) -> VerificationState:
    path = Path(state["dossier_path"])
    if path.suffix.lower() in NARRATIVE_SUFFIXES:
        return _extract_narrative(path)
    return _extract_structured(path)
