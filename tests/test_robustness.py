from cmc_verifier import build_graph
from cmc_verifier.nodes import checks
from cmc_verifier.nodes.safety import isolate


def test_isolate_converts_crash_to_flag():
    def boom(state):
        raise RuntimeError("kaput")
    out = isolate("boom", boom)({})
    assert len(out["flags"]) == 1
    assert "crashed" in out["flags"][0].message


def test_bad_and_empty_sources_flagged_not_fatal(tmp_path):
    dossier = tmp_path / "dossier.json"
    dossier.write_text("[]", encoding="utf-8")
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    out = build_graph().invoke({"dossier_path": str(dossier), "source_paths": [str(bad), str(empty)]})
    msgs = [f.message for f in out["adjudicated_flags"]]
    assert any("bad.json" in m and "could not be parsed" in m for m in msgs)
    assert any("empty.csv" in m and "no facts" in m for m in msgs)


def test_crashing_check_does_not_abort_run(tmp_path, monkeypatch):
    dossier = tmp_path / "dossier.json"
    dossier.write_text("[]", encoding="utf-8")
    def boom(state):
        raise ValueError("x")
    monkeypatch.setitem(checks.CHECKS, "traceability", boom)
    out = build_graph().invoke({"dossier_path": str(dossier), "source_paths": []})
    assert any("crashed" in f.message for f in out["adjudicated_flags"])


def test_source_out_of_spec_masked_by_claim(tmp_path):
    import json
    dossier = tmp_path / "d.json"
    dossier.write_text(json.dumps([{
        "analyte": "Assay", "batch_id": "B1", "quantitative_value": 99.0,
        "ctd_section": "3.2.P.5.4", "claim_type": "quantitative", "text_span": "Assay 99.0%"}]), encoding="utf-8")
    src = tmp_path / "s.json"
    src.write_text(json.dumps([
        {"analyte": "Assay", "batch_id": "B1", "result": 92.0, "unit": "%",
         "spec_limit": "95.0-105.0",
         "source_ref": {"document_id": "s", "page": 1, "location": "r1"}}]), encoding="utf-8")
    out = build_graph().invoke({"dossier_path": str(dossier), "source_paths": [str(src)]})
    assert any("source result" in f.message and "violates" in f.message for f in out["adjudicated_flags"])


def _link(claim_kw=None, result_unit="%", spec_unit="%"):
    from cmc_verifier.models import Claim, SourceFact, SourceRef
    ref = SourceRef(document_id="d")
    c = Claim(text_span="x", ctd_section="3.2.P.5.1", claim_type="quantitative",
              analyte="Water", batch_id="B1", quantitative_value=1.0)
    rf = SourceFact(analyte="Water Content", result=1.0, unit=result_unit, batch_id="B1", source_ref=ref)
    sf = SourceFact(analyte="Water Content", spec_limit="NMT 4.0", unit=spec_unit, source_ref=ref)
    return {"links": [{"claim": c, "result_fact": rf, "spec_fact": sf}]}


def test_unit_mismatch_and_nonstandard_name_flagged():
    out = checks.check_unit_nomenclature(_link(result_unit="mg/g", spec_unit="%"))
    msgs = [f.message for f in out["flags"]]
    assert any("differs from specification unit" in m for m in msgs)
    assert any("Non-standard analyte name" in m for m in msgs)


def test_matching_units_clean():
    out = checks.check_unit_nomenclature(_link())
    assert not any("differs" in f.message for f in out["flags"])


def test_missing_required_section_flagged():
    out = checks.check_completeness_ctd({"claims": [], "source_facts": []})
    assert {f.dossier_ref for f in out["flags"]} == set(checks.REQUIRED_CTD_SECTIONS)
