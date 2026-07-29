"""Extraction-accuracy eval (ARCHITECTURE.md §5).

The ground truth for the messy CoA CSV lives in coa_B001.expected.json — the same
hand-authored facts we used before the parser existed. Now they're the answer key
that MEASURES the parser, not a stand-in for it.

Precision/recall on extraction is the number that proves the moat. Keep it at 1.0
as you make the source documents progressively uglier.
"""

import json
from pathlib import Path

from cmc_verifier.adapters import parse_coa_csv, parse_value

SOURCES = Path(__file__).parent.parent / "data" / "sample" / "sources"
CSV = SOURCES / "coa_B001.csv"
TRUTH = SOURCES / "coa_B001.expected.json"


def _key(f):
    """Compare on the fields that matter; ignore source_ref (provenance varies)."""
    return (f["analyte"], f["method"], round(f["result"], 6), f["unit"], f["batch_id"])


def test_parse_value_strips_units():
    assert parse_value("99.2 %") == (99.2, "%")
    assert parse_value("0.32%") == (0.32, "%")
    assert parse_value(" 3.1 %") == (3.1, "%")
    assert parse_value("not a number") == (None, None)


def test_extraction_matches_ground_truth():
    got = [f.model_dump() for f in parse_coa_csv(CSV)]
    want = json.loads(TRUTH.read_text())

    got_keys = {_key(f) for f in got}
    want_keys = {_key(f) for f in want}

    true_positives = len(got_keys & want_keys)
    precision = true_positives / len(got_keys) if got_keys else 0.0
    recall = true_positives / len(want_keys) if want_keys else 0.0

    assert precision == 1.0, f"precision {precision}: spurious {got_keys - want_keys}"
    assert recall == 1.0, f"recall {recall}: missed {want_keys - got_keys}"


def test_every_fact_carries_provenance():
    """The invariant: no value without a source pointer."""
    for f in parse_coa_csv(CSV):
        assert f.source_ref.document_id
        assert f.source_ref.location


def test_preamble_is_not_extracted_as_a_fact():
    """Title/product rows above the table must not become facts."""
    analytes = {f.analyte for f in parse_coa_csv(CSV)}
    assert analytes == {"Assay", "Related Substances - Total", "Water Content"}