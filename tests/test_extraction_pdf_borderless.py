"""Borderless-PDF extraction eval (ARCHITECTURE.md §5).

The hard case: a table with no ruling lines, recovered by text-alignment. If the
fixture is missing, generate it first:
    python scripts/make_borderless_pdf.py
"""

import json
from pathlib import Path

import pytest

from cmc_verifier.adapters import parse_coa_pdf

SOURCES = Path(__file__).parent.parent / "data" / "sample" / "sources"
PDF = SOURCES / "coa_B008.pdf"
TRUTH = SOURCES / "coa_B008.expected.json"

pytestmark = pytest.mark.skipif(not PDF.exists(),
                                reason="run scripts/make_borderless_pdf.py to create the fixture")


def _key(f):
    r = f.get("result")
    return (f["analyte"], f.get("method"), None if r is None else round(r, 6),
            f.get("unit"), f.get("batch_id"), f.get("qualifier"), f.get("result_text"))


def test_borderless_extraction_matches_ground_truth():
    got = [f.model_dump() for f in parse_coa_pdf(PDF)]
    want = json.loads(TRUTH.read_text())
    gk = {_key(f) for f in got}; wk = {_key(f) for f in want}
    tp = len(gk & wk)
    assert tp / len(gk) == 1.0, f"spurious: {gk - wk}"
    assert tp / len(wk) == 1.0, f"missed: {wk - gk}"


def test_borderless_batch_captured():
    assert {f.batch_id for f in parse_coa_pdf(PDF)} == {"B-008"}