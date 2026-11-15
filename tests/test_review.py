import json

import pytest

from cmc_verifier import build_graph
from cmc_verifier.audit import AuditLog, verify_audit_log
from cmc_verifier.nodes.review import Decision, flag_id, make_decision


def _dossier_and_source(tmp_path):
    d = tmp_path / "d.json"
    d.write_text(json.dumps([{
        "analyte": "Assay", "batch_id": "B1", "quantitative_value": 99.0,
        "ctd_section": "3.2.P.5.1", "claim_type": "quantitative", "text_span": "Assay 99.0%"}]),
        encoding="utf-8")
    s = tmp_path / "s.json"
    s.write_text(json.dumps([{
        "analyte": "Assay", "batch_id": "B1", "result": 90.0, "unit": "%", "spec_limit": "95.0-105.0",
        "source_ref": {"document_id": "s", "page": 1}}]), encoding="utf-8")
    return d, s


def test_graph_pauses_before_review_then_resumes_with_decisions(tmp_path):
    d, s = _dossier_and_source(tmp_path)
    app = build_graph(interactive=True)
    cfg = {"configurable": {"thread_id": "t1"}}
    paused = app.invoke({"dossier_path": str(d), "source_paths": [str(s)]}, cfg)
    assert paused["report"].get("status") != "reviewed"
    assert app.get_state(cfg).next == ("human_review",)       # genuinely interrupted

    flags = paused["adjudicated_flags"]
    assert flags
    decisions = [make_decision(f, Decision.ACCEPT, "alice") for f in flags]
    app.update_state(cfg, {"decisions": decisions})
    final = app.invoke(None, cfg)
    assert final["report"]["status"] == "reviewed"
    assert final["report"]["decisions"]["accept"] == len(flags)


def test_partial_decisions_stay_awaiting(tmp_path):
    d, s = _dossier_and_source(tmp_path)
    app = build_graph(interactive=True)
    cfg = {"configurable": {"thread_id": "t2"}}
    paused = app.invoke({"dossier_path": str(d), "source_paths": [str(s)]}, cfg)
    flags = paused["adjudicated_flags"]
    assert len(flags) >= 2
    app.update_state(cfg, {"decisions": [make_decision(flags[0], Decision.DISMISS, "bob", "fp")]})
    final = app.invoke(None, cfg)
    assert final["report"]["status"] == "awaiting_human_review"


def test_decision_requires_reviewer_and_valid_value(tmp_path):
    d, s = _dossier_and_source(tmp_path)
    flag = build_graph().invoke({"dossier_path": str(d), "source_paths": [str(s)]})["adjudicated_flags"][0]
    with pytest.raises(ValueError):
        make_decision(flag, Decision.ACCEPT, "  ")
    with pytest.raises(ValueError):
        make_decision(flag, "maybe", "alice")


def test_flag_id_is_stable(tmp_path):
    d, s = _dossier_and_source(tmp_path)
    run = lambda: build_graph().invoke({"dossier_path": str(d), "source_paths": [str(s)]})
    assert [flag_id(f) for f in run()["adjudicated_flags"]] == [flag_id(f) for f in run()["adjudicated_flags"]]


def test_decisions_written_to_audit_chain(tmp_path):
    d, s = _dossier_and_source(tmp_path)
    flag = build_graph().invoke({"dossier_path": str(d), "source_paths": [str(s)]})["adjudicated_flags"][0]
    log_path = tmp_path / "a.jsonl"
    audit = AuditLog(log_path)
    audit.decision_recorded(make_decision(flag, Decision.NEEDS_INFO, "carol", "ask QC"))
    audit.run_completed({})
    events = [json.loads(ln) for ln in log_path.read_text(encoding="utf-8").splitlines()]
    assert events[0]["event"] == "decision_recorded" and events[0]["reviewer"] == "carol"
    assert verify_audit_log(log_path)[0]
