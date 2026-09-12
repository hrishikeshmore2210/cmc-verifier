"""Entrypoint. Run from the repo root:

    python run.py                 # run pipeline, print flags + JSON report
    python run.py --report        # also write report.html
    python run.py --audit run.jsonl   # override audit-log path (default: audit_log.jsonl)

Every run appends to an append-only audit trail.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cmc_verifier import build_graph
from cmc_verifier.audit import AuditLog
from cmc_verifier.mcp_store import LocalDocumentStore
from cmc_verifier.nodes.checks import CHECKS

SAMPLE_DIR = Path(__file__).parent / "data" / "sample"
SOURCES_DIR = SAMPLE_DIR / "sources"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the CMC verification pipeline.")
    parser.add_argument("--report", nargs="?", const="report.html", default=None,
                        help="also write an HTML discrepancy report (default: report.html)")
    parser.add_argument("--audit", default="audit_log.jsonl",
                        help="append-only audit-trail path (default: audit_log.jsonl)")
    args = parser.parse_args()

    store = LocalDocumentStore(SOURCES_DIR)
    source_paths = [str(p) for p in store.list_documents()
                    if p.suffix.lower() in {".csv", ".pdf", ".json"}
                    and not p.name.endswith(".expected.json")]

    dossier_path = SAMPLE_DIR / "dossier.json"

    audit = AuditLog(args.audit)
    audit.run_started(dossier_path, source_paths, CHECKS.keys())

    initial_state = {
        "dossier_path": str(dossier_path),
        "source_paths": source_paths,
        "flags": [],
    }

    app = build_graph()
    print("\n--- running verification pipeline ---")
    final_state = app.invoke(initial_state)
    print("--- done ---\n")

    # Record the run as append-only audit events, reconstructed from final state.
    audit.ingested(len(final_state.get("source_facts", [])), len(source_paths))
    audit.claims_extracted(len(final_state.get("claims", [])))
    for f in final_state.get("adjudicated_flags", []):
        audit.flag_raised(f)
    audit.run_completed(final_state.get("report", {}))

    print("FLAGS")
    for f in final_state.get("adjudicated_flags", []):
        print(f"  [{f.severity.value.upper():8}] {f.check_name}: {f.message}")

    print("\nDISCREPANCY REPORT")
    print(json.dumps(final_state.get("report", {}), indent=2))

    if args.report:
        from cmc_verifier.report import render_html_report
        html_str = render_html_report(final_state.get("report", {}),
                                      final_state.get("adjudicated_flags", []))
        Path(args.report).write_text(html_str, encoding="utf-8")
        print(f"\nWrote HTML report to {args.report}")

    print(f"Audit trail appended to {args.audit} (run_id {audit.run_id})")


if __name__ == "__main__":
    main()