"""Unit tests for measurement reconciliation (ARCHITECTURE.md §3).

The truth table for the numerical check: value, qualifier, and result-type
disagreements between a dossier claim and its source of record.
"""

from cmc_verifier.models import Claim, SourceFact, SourceRef
from cmc_verifier.nodes.checks import reconcile_measurement


def C(value=None, qualifier=None, result_text=None):
    return Claim(text_span="", ctd_section="3.2.P.5.1", claim_type="quantitative",
                 analyte="X", batch_id="B", quantitative_value=value,
                 qualifier=qualifier, result_text=result_text)


def F(result=None, qualifier=None, result_text=None, unit="%"):
    return SourceFact(analyte="X", result=result, qualifier=qualifier,
                      result_text=result_text, unit=unit, batch_id="B",
                      source_ref=SourceRef(document_id="doc"))


def test_matching_values_no_flag():
    assert reconcile_measurement(C(value=99.2), F(result=99.2)) is None


def test_value_mismatch_flags():
    assert reconcile_measurement(C(value=0.23), F(result=0.32)) is not None


def test_qualifier_mismatch_flags():
    # same value but the dossier adds a "<" the source does not have
    assert reconcile_measurement(C(value=2.5, qualifier="<"), F(result=2.5)) is not None
    # matching qualifiers agree
    assert reconcile_measurement(C(value=0.6, qualifier=">"), F(result=0.6, qualifier=">")) is None


def test_result_type_mismatch_flags():
    # dossier says ND, source has a number
    assert reconcile_measurement(C(result_text="ND"), F(result=99.5)) is not None
    # both ND agree
    assert reconcile_measurement(C(result_text="ND"), F(result_text="ND")) is None


def test_within_tolerance_no_flag():
    assert reconcile_measurement(C(value=99.200004), F(result=99.2)) is None