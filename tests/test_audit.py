"""Audit-trail tests: append-only, sequenced, versioned, provenance-carrying."""

import json

from cmc_verifier.audit import AuditLog
from cmc_verifier.models import Flag, Severity, SourceRef


def _read(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_events_are_appended_as_jsonl(tmp_path):
    p = tmp_path / "audit.jsonl"
    log = AuditLog(p)
    log.run_started("dossier.json", ["a.csv"], ["numerical_reconciliation"])
    log.ingested(5, 1)
    log.run_completed({"total_flags": 0})
    records = _read(p)
    assert [r["event"] for r in records] == ["run_started", "ingested", "run_completed"]


def test_records_have_required_fields(tmp_path):
    p = tmp_path / "audit.jsonl"
    AuditLog(p).ingested(3, 2)
    r = _read(p)[0]
    for field in ("seq", "ts", "run_id", "schema_version", "pipeline_version", "event"):
        assert field in r


def test_sequence_increments(tmp_path):
    p = tmp_path / "audit.jsonl"
    log = AuditLog(p)
    log.ingested(1, 1); log.claims_extracted(2); log.run_completed({})
    assert [r["seq"] for r in _read(p)] == [1, 2, 3]


def test_append_only_across_runs(tmp_path):
    p = tmp_path / "audit.jsonl"
    AuditLog(p).ingested(1, 1)     # first run
    AuditLog(p).ingested(2, 1)     # second run must append, not truncate
    assert len(_read(p)) == 2


def test_flag_raised_captures_provenance(tmp_path):
    p = tmp_path / "audit.jsonl"
    flag = Flag(check_name="numerical_reconciliation", severity=Severity.MAJOR,
                message="x", dossier_ref="3.2.P.5.4",
                source_ref=SourceRef(document_id="CoA-B006", page=1, location="row 1"),
                confidence=0.95, rationale="r")
    AuditLog(p).flag_raised(flag)
    r = _read(p)[0]
    assert r["event"] == "flag_raised"
    assert r["check"] == "numerical_reconciliation"
    assert r["source_ref"]["document_id"] == "CoA-B006"
    assert r["source_ref"]["location"] == "row 1"