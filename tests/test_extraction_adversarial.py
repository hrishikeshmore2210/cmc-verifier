"""Adversarial extraction eval (ARCHITECTURE.md §5).

Proves the parser survives the ugly CoA and keeps precision/recall at 1.0.
Every new mess you add to the CSV should get a matching entry in the answer key
and stay green here — that green bar IS the moat, made measurable.
"""

import json
from pathlib import Path

from cmc_verifier.adapters import canonical_analyte, parse_coa_csv, parse_measurement

SOURCES = Path(__file__).parent.parent / "data" / "sample" / "sources"
CSV = SOURCES / "coa_B003_B004.csv"
TRUTH = SOURCES / "coa_B003_B004.expected.json"


def _key(f):
    r = f.get("result")
    return (
        f["analyte"], f.get("method"),
        None if r is None else round(r, 6),
        f.get("unit"), f.get("batch_id"),
        f.get("qualifier"), f.get("result_text"),
    )


def test_measurement_parsing_edge_cases():
    assert parse_measurement("< 0.05 %") == ("<", 0.05, "%", None)
    assert parse_measurement("ND") == (None, None, None, "ND")
    assert parse_measurement("N/D") == (None, None, None, "ND")
    assert parse_measurement("Not Detected") == (None, None, None, "ND")
    assert parse_measurement("101.4 %") == (None, 101.4, "%", None)


def test_analyte_alias_resolves():
    assert canonical_analyte("Water") == "Water Content"
    assert canonical_analyte(" Assay ") == "Assay"


def test_adversarial_extraction_matches_ground_truth():
    got = [f.model_dump() for f in parse_coa_csv(CSV)]
    want = json.loads(TRUTH.read_text())

    got_keys = {_key(f) for f in got}
    want_keys = {_key(f) for f in want}
    tp = len(got_keys & want_keys)
    precision = tp / len(got_keys) if got_keys else 0.0
    recall = tp / len(want_keys) if want_keys else 0.0

    assert precision == 1.0, f"spurious facts: {got_keys - want_keys}"
    assert recall == 1.0, f"missed facts: {want_keys - got_keys}"


def test_multiple_batches_captured():
    batches = {f.batch_id for f in parse_coa_csv(CSV)}
    assert batches == {"B-003", "B-004"}


def test_footer_and_subheaders_not_extracted():
    analytes = {f.analyte for f in parse_coa_csv(CSV)}
    for junk in ("Reviewed by", "Approved by", "Page", "Impurities"):
        assert junk not in analytes
