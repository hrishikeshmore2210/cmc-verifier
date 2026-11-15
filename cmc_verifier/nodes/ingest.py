"""Ingestion & normalization (ARCHITECTURE.md §2.1) — the moat.

Routes each source document to the adapter for its format, and returns a single
normalized list[SourceFact]. The output contract never changes, so adding a new
format (PDF, XLSX, vision-extracted scan) means adding an adapter here and
nothing else in the graph moves.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from ..adapters import parse_coa_csv, parse_coa_pdf
from ..models import Flag, Severity, SourceFact, VerificationState

log = logging.getLogger(__name__)


def _parse_json(path: Path) -> list[SourceFact]:
    return [SourceFact(**row) for row in json.loads(path.read_text(encoding="utf-8-sig"))]


# Extension -> adapter.
ADAPTERS = {
    ".csv": parse_coa_csv,
    ".json": _parse_json,
    ".pdf": parse_coa_pdf,
}


def _ingest_flag(path: Path, problem: str) -> Flag:
    return Flag(
        check_name="ingest",
        severity=Severity.MAJOR,
        message=f"Source document '{path.name}' {problem}",
        confidence=1.0,
        rationale="Claims relying on this document cannot be verified; do not treat as clean.",
    )


def ingest(state: VerificationState) -> VerificationState:
    facts: list[SourceFact] = []
    skipped: list[str] = []
    flags: list[Flag] = []

    for p in state.get("source_paths", []):
        path = Path(p)
        adapter = ADAPTERS.get(path.suffix.lower())
        if adapter is None:
            skipped.append(path.name)
            continue
        try:
            parsed = adapter(path)
        except Exception as exc:  # noqa: BLE001 - one bad file must not sink the run
            log.error(f"FAILED {path.name}: {type(exc).__name__}: {exc}")
            flags.append(_ingest_flag(path, f"could not be parsed ({type(exc).__name__}: {exc})"))
            continue
        if not parsed:
            flags.append(_ingest_flag(path, "yielded no facts (empty, unrecognized layout, or scanned image)"))
        facts.extend(parsed)
        log.info(f"{path.name}: {len(parsed)} fact(s) via {path.suffix} adapter")
    if skipped:
        log.info(f"skipped (no adapter): {', '.join(skipped)}")
    log.info(f"loaded {len(facts)} source fact(s) total")
    return {"source_facts": facts, "flags": flags}