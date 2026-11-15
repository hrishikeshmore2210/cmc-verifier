from cmc_verifier.models import Claim, SourceFact, SourceRef
from cmc_verifier.nodes.ground import ground


def _fact(doc, result, batch="B-001", analyte="Water Content", spec=None):
    return SourceFact(analyte=analyte, result=result, unit="%", batch_id=batch, spec_limit=spec,
                      source_ref=SourceRef(document_id=doc))


def _claim(analyte="Water", batch="b001", value=0.5):
    return Claim(text_span="x", ctd_section="3.2.P.5.1", claim_type="quantitative",
                 analyte=analyte, batch_id=batch, quantitative_value=value)


def test_alias_and_batch_punctuation_normalized():
    out = ground({"claims": [_claim()], "source_facts": [_fact("a", 0.5)]})
    assert out["links"][0]["result_fact"] is not None


def test_conflicting_sources_flagged():
    out = ground({"claims": [_claim()], "source_facts": [_fact("a", 0.5), _fact("b", 0.9)]})
    assert any("conflicting source results" in f.message for f in out["flags"])


def test_null_keys_never_match():
    c = _claim(analyte=None, batch=None)
    f = SourceFact(analyte=None, result=1.0, batch_id=None, source_ref=SourceRef(document_id="a"))
    assert ground({"claims": [c], "source_facts": [f]})["links"][0]["result_fact"] is None


def test_conflicting_specs_flagged():
    out = ground({"claims": [_claim()], "source_facts": [
        _fact("a", 0.5, spec="NMT 1.0"), _fact("b", 0.5, spec="NMT 0.5")]})
    assert any("conflicting specifications" in f.message for f in out["flags"])


def test_page_marker_sets_source_page():
    from cmc_verifier.adapters import _PAGE_MARKER, facts_from_rows
    rows = [
        [_PAGE_MARKER, "1"], ["Batch No.", "B/001_A"],
        ["Test", "Result", "Units"], ["Assay", "99.0", "%"],
        [_PAGE_MARKER, "2"], ["Water", "0.3", "%"],
    ]
    facts = facts_from_rows(rows, "doc")
    assert [f.source_ref.page for f in facts] == [1, 2]
    assert facts[0].batch_id == "B/001_A"
