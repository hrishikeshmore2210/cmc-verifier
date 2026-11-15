"""Machine-readable exports: plain JSON and SARIF 2.1.0 (for GitHub code scanning,
Azure DevOps, and other tools that ingest SARIF)."""

from __future__ import annotations

from .models import Severity
from .nodes.review import flag_id

SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
_SARIF_LEVEL = {Severity.CRITICAL: "error", Severity.MAJOR: "warning", Severity.MINOR: "note"}
_RANK = {Severity.MINOR: 1, Severity.MAJOR: 2, Severity.CRITICAL: 3}


def severity_rank(sev) -> int:
    return _RANK[Severity(sev)]


def flags_to_json(report: dict, flags) -> dict:
    return {
        "report": report,
        "flags": [
            {
                "flag_id": flag_id(f),
                "check": f.check_name,
                "severity": Severity(f.severity).value,
                "message": f.message,
                "dossier_ref": f.dossier_ref,
                "source_ref": None if f.source_ref is None else f.source_ref.model_dump(),
                "confidence": f.confidence,
                "rationale": f.rationale,
            }
            for f in flags
        ],
    }


def flags_to_sarif(flags, tool_version: str) -> dict:
    rules = sorted({f.check_name for f in flags})
    results = []
    for f in flags:
        result = {
            "ruleId": f.check_name,
            "level": _SARIF_LEVEL[Severity(f.severity)],
            "message": {"text": f.message},
            "partialFingerprints": {"flagId": flag_id(f)},
            "properties": {"dossier_ref": f.dossier_ref, "confidence": f.confidence,
                           "rationale": f.rationale},
        }
        if f.source_ref is not None:
            region = {"startLine": f.source_ref.page} if f.source_ref.page else {}
            result["locations"] = [{
                "physicalLocation": {
                    "artifactLocation": {"uri": f.source_ref.document_id},
                    **({"region": region} if region else {}),
                },
                "message": {"text": f.source_ref.location or ""},
            }]
        results.append(result)
    return {
        "$schema": SARIF_SCHEMA,
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {
                "name": "cmc-verifier",
                "version": tool_version,
                "rules": [{"id": r, "name": r} for r in rules],
            }},
            "results": results,
        }],
    }
