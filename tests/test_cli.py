import json

import pytest

from cmc_verifier.audit import verify_audit_log
from cmc_verifier.cli import main


@pytest.fixture
def audit_path(tmp_path):
    return str(tmp_path / "audit.jsonl")


def test_sample_run_fails_on_critical_by_default(audit_path):
    assert main(["--audit", audit_path]) == 1          # sample data contains critical flags


def test_fail_on_none_exits_zero(audit_path):
    assert main(["--audit", audit_path, "--fail-on", "none"]) == 0


def test_json_and_sarif_exports(tmp_path, audit_path):
    out_json, out_sarif = tmp_path / "o.json", tmp_path / "o.sarif"
    main(["--audit", audit_path, "--fail-on", "none", "--json", str(out_json), "--sarif", str(out_sarif)])
    data = json.loads(out_json.read_text(encoding="utf-8"))
    sarif = json.loads(out_sarif.read_text(encoding="utf-8"))
    assert len(data["flags"]) == data["report"]["total_flags"] == 13
    assert sarif["version"] == "2.1.0"
    results = sarif["runs"][0]["results"]
    assert len(results) == 13
    assert {r["level"] for r in results} <= {"error", "warning", "note"}
    assert all("flagId" in r["partialFingerprints"] for r in results)


def test_audit_ledger_valid_after_run(audit_path):
    main(["--audit", audit_path, "--fail-on", "none"])
    assert verify_audit_log(audit_path) == (True, [])


def test_missing_dossier_is_usage_error(tmp_path, audit_path):
    assert main(["--audit", audit_path, "--dossier", str(tmp_path / "nope.json")]) == 2


def test_empty_sources_is_usage_error(tmp_path, audit_path):
    assert main(["--audit", audit_path, "--sources", str(tmp_path)]) == 2


def test_review_requires_reviewer(audit_path):
    assert main(["--audit", audit_path, "--review"]) == 2


def test_internal_error_returns_3_and_ledger_records_failure(tmp_path, audit_path):
    bad = tmp_path / "bad_dossier.json"
    bad.write_text("{not json", encoding="utf-8")
    assert main(["--audit", audit_path, "--dossier", str(bad)]) == 3
    events = [json.loads(ln)["event"] for ln in open(audit_path, encoding="utf-8")]
    assert events == ["run_started", "run_failed"]
    assert verify_audit_log(audit_path)[0]


def test_interactive_review_records_decisions(tmp_path, audit_path):
    answers = iter(["a", "looks real", "d", "fp"] + ["s"] * 50)
    code = main(["--audit", audit_path, "--fail-on", "none", "--review", "--reviewer", "alice"],
                input_fn=lambda prompt="": next(answers))
    assert code == 0
    events = [json.loads(ln) for ln in open(audit_path, encoding="utf-8")]
    decisions = [e for e in events if e["event"] == "decision_recorded"]
    assert [d["decision"] for d in decisions] == ["accept", "dismiss"]
    assert all(d["reviewer"] == "alice" for d in decisions)
    assert verify_audit_log(audit_path)[0]
