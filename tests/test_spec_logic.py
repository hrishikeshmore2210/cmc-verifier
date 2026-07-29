"""Unit tests for spec-vs-result verdict logic (ARCHITECTURE.md §3).

Pure function, no graph — the truth table for qualifiers and non-numeric results.
"""

from cmc_verifier.nodes.checks import evaluate_against_spec, parse_spec_limit


def E(value=None, qualifier=None, result_text=None, spec="NMT 0.5"):
    low, high = parse_spec_limit(spec)
    return evaluate_against_spec(value, qualifier, result_text, low, high)


def test_numeric_within_and_outside():
    assert E(value=0.2, spec="NMT 0.5") == "pass"
    assert E(value=0.7, spec="NMT 0.5") == "violation"
    assert E(value=99.2, spec="95.0-105.0") == "pass"
    assert E(value=93.5, spec="95.0-105.0") == "violation"


def test_less_than_qualifier():
    assert E(value=0.05, qualifier="<", spec="NMT 0.5") == "pass"           # below upper limit
    assert E(value=0.6, qualifier="<", spec="NMT 0.5") == "indeterminate"   # straddles limit
    assert E(value=0.05, qualifier="<", spec="NLT 0.1") == "violation"      # below lower bound


def test_greater_than_qualifier():
    assert E(value=0.6, qualifier=">", spec="NMT 0.5") == "violation"           # above upper limit
    assert E(value=96.0, qualifier=">", spec="NLT 95.0") == "pass"             # above lower bound
    assert E(value=96.0, qualifier=">", spec="95.0-105.0") == "indeterminate"  # could exceed upper


def test_not_detected():
    assert E(result_text="ND", spec="NMT 0.5") == "pass"          # ND fine for upper-only limit
    assert E(result_text="ND", spec="95.0-105.0") == "violation"  # ND fails an assay lower bound
    assert E(result_text="ND", spec="NLT 95.0") == "violation"
