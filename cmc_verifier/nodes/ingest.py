"""Ingestion & normalization (ARCHITECTURE.md §2.1) — the moat.

Routes each source document to the adapter for its format, and returns a single
normalized list[SourceFact]. The output contract never changes, so adding a new
format (PDF, XLSX, vision-extracted scan) means adding an adapter here and
nothing else in the graph moves.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..adapters import parse_coa_csv, parse_coa_pdf
from ..models import SourceFact, VerificationState


def _parse_json(path: Path) -> list[SourceFact]:
    return [SourceFact(**row) for row in json.loads(path.read_text())]


# Extension -> adapter. Add ".pdf": parse_coa_pdf here later.
ADAPTERS = {
    ".csv": parse_coa_csv,
    ".json": _parse_json,
    ".pdf": parse_coa_pdf,
}


def ingest(state: VerificationState) -> VerificationState:
    facts: list[SourceFact] = []
    skipped: list[str] = []

    for p in state.get("source_paths", []):
        path = Path(p)
        adapter = ADAPTERS.get(path.suffix.lower())
        if adapter is None:
            skipped.append(path.name)
            continue
        parsed = adapter(path)
        facts.extend(parsed)
        print(f"[ingest]   {path.name}: {len(parsed)} fact(s) via {path.suffix} adapter")

    if skipped:
        print(f"[ingest]   skipped (no adapter): {', '.join(skipped)}")
    print(f"[ingest] loaded {len(facts)} source fact(s) total")
    return {"source_facts": facts}