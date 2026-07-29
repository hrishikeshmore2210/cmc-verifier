"""Unit tests for cross-section consistency (ARCHITECTURE.md §3).

The same analyte+batch stated in different dossier sections must agree.
"""

from cmc_verifier.models import Claim
from cmc_verifier.nodes.checks import check_cross_section_consistency


def C(analyte, batch, section, value=None, qualifier=None, result_text=None):
    return Claim(text_span="", ctd_section=section, claim_type="quantitative",
                 analyte=analyte, batch_id=batch, quantitative_value=value,
                 qualifier=qualifier, result_text=result_text)


def _flags(claims):
    return check_cross_section_consistency({"claims": claims})["flags"]


def test_consistent_across_sections_no_flag():
    assert _flags([C("Assay", "B", "3.2.P.5.4", value=99.0),
                   C("Assay", "B", "3.2.P.2.3", value=99.0)]) == []


def test_inconsistent_across_sections_flags():
    assert len(_flags([C("Assay", "B", "3.2.P.5.4", value=99.0),
                       C("Assay", "B", "3.2.P.2.3", value=97.5)])) == 1


def test_single_mention_no_flag():
    assert _flags([C("Assay", "B", "3.2.P.5.4", value=99.0)]) == []


def test_conflict_within_one_section_is_not_cross_section():
    assert _flags([C("Assay", "B", "3.2.P.5.4", value=99.0),
                   C("Assay", "B", "3.2.P.5.4", value=97.5)]) == []


def test_qualifier_or_nd_difference_flags():
    assert len(_flags([C("Imp", "B", "3.2.P.5.4", result_text="ND"),
                       C("Imp", "B", "3.2.P.2.3", value=0.1)])) == 1