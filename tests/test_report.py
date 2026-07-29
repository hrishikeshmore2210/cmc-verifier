"""Report renderer tests."""

from cmc_verifier.models import Flag, Severity, SourceRef
from cmc_verifier.report import render_html_report


def _flags():
    return [
        Flag(check_name="spec_vs_result", severity=Severity.CRITICAL,
             message="Assay (B-002): reported 93.5% violates specification '95.0-105.0'",
             dossier_ref="3.2.P.5.1",
             source_ref=SourceRef(document_id="SPEC-DP-01", page=1),
             confidence=0.97, rationale="Spec-vs-result verdict: violation."),
        Flag(check_name="numerical_reconciliation", severity=Severity.MAJOR,
             message="Water Content (B-006): qualifier mismatch: dossier states <2.5%, source reports 2.5%",
             dossier_ref="3.2.P.5.4",
             source_ref=SourceRef(document_id="CoA-B006", page=1, location="row 1"),
             confidence=0.95, rationale="Reported measurement does not match the source of record."),
    ]


def _report():
    return {"total_flags": 2,
            "by_severity": {"critical": 1, "major": 1, "minor": 0},
            "by_check": {"spec_vs_result": 1, "numerical_reconciliation": 1}}


def test_report_is_html_and_contains_flags():
    doc = render_html_report(_report(), _flags())
    assert doc.startswith("<!doctype html>")
    assert "spec_vs_result" in doc
    assert "CRITICAL" in doc
    assert "3.2.P.5.1" in doc
    assert "SPEC-DP-01" in doc


def test_report_escapes_angle_brackets():
    # messages contain '<' (e.g. "<2.5%") — must be HTML-escaped, not raw
    doc = render_html_report(_report(), _flags())
    assert "&lt;2.5%" in doc
    assert "<2.5%" not in doc


def test_empty_report_says_clean():
    doc = render_html_report({"total_flags": 0, "by_severity": {}}, [])
    assert "No discrepancies found." in doc