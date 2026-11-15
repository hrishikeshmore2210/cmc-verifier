"""Command-line interface.

    python run.py                                  # sample data, exit 1 if any CRITICAL flag
    python run.py --fail-on major                  # stricter gate
    python run.py --dossier d.json --sources dir/  # your own data
    python run.py --json out.json --sarif out.sarif --report report.html
    python run.py --review --reviewer alice        # pause for human decisions

Exit codes: 0 ok · 1 flags at/above --fail-on · 2 usage/input error · 3 internal error.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from pathlib import Path

from . import build_graph
from .audit import PIPELINE_VERSION, AuditLog
from .config import get_settings
from .exports import flags_to_json, flags_to_sarif, severity_rank
from .logging_setup import configure_logging
from .mcp_store import LocalDocumentStore
from .nodes.checks import CHECKS
from .nodes.review import Decision, flag_id, make_decision

log = logging.getLogger(__name__)

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample"
SOURCE_SUFFIXES = {".csv", ".pdf", ".json"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cmc-verify", description="Run the CMC verification pipeline.")
    p.add_argument("--dossier", default=str(SAMPLE_DIR / "dossier.json"), help="dossier claims JSON")
    p.add_argument("--sources", default=str(SAMPLE_DIR / "sources"), help="directory of source documents")
    p.add_argument("--report", nargs="?", const="report.html", default=None, help="write an HTML report")
    p.add_argument("--json", dest="json_out", default=None, help="write flags + report as JSON")
    p.add_argument("--sarif", default=None, help="write flags as SARIF 2.1.0")
    p.add_argument("--audit", default=None, help="audit ledger path (default: CMC_AUDIT_PATH or audit_log.jsonl)")
    p.add_argument("--fail-on", choices=["none", "minor", "major", "critical"], default="critical",
                   help="exit 1 if any flag is at/above this severity (default: critical)")
    p.add_argument("--review", action="store_true", help="pause for interactive human decisions")
    p.add_argument("--reviewer", default=None, help="reviewer identity (required with --review)")
    return p


def _collect_sources(sources_dir: str) -> list[str]:
    store = LocalDocumentStore(sources_dir)
    return [str(p) for p in store.list_documents()
            if p.suffix.lower() in SOURCE_SUFFIXES and not p.name.endswith(".expected.json")]


def _interactive_review(app, cfg, flags, reviewer, audit, input_fn=input) -> None:
    keys = {"a": Decision.ACCEPT, "d": Decision.DISMISS, "n": Decision.NEEDS_INFO}
    decisions = []
    for i, f in enumerate(flags, start=1):
        print(f"\n[{i}/{len(flags)}] [{f.severity.value.upper()}] {f.check_name}: {f.message}")
        while True:
            ans = input_fn("  (a)ccept / (d)ismiss / (n)eeds info / (s)kip > ").strip().lower()
            if ans in keys or ans == "s":
                break
        if ans == "s":
            continue
        note = input_fn("  note (optional) > ").strip()
        d = make_decision(f, keys[ans], reviewer, note)
        audit.decision_recorded(d)
        decisions.append(d)
    app.update_state(cfg, {"decisions": decisions})


def main(argv=None, input_fn=input) -> int:
    args = build_parser().parse_args(argv)
    settings = get_settings()
    run_id = uuid.uuid4().hex[:12]
    configure_logging(run_id=run_id, level=settings.log_level, json_logs=settings.log_json)

    if args.review and not (args.reviewer and args.reviewer.strip()):
        print("error: --review requires --reviewer <name>", file=sys.stderr)
        return 2
    if not Path(args.dossier).is_file():
        print(f"error: dossier not found: {args.dossier}", file=sys.stderr)
        return 2
    source_paths = _collect_sources(args.sources)
    if not source_paths:
        print(f"error: no source documents (.csv/.pdf/.json) found in {args.sources}", file=sys.stderr)
        return 2

    audit = AuditLog(args.audit or settings.audit_path, run_id=run_id)
    audit.run_started(args.dossier, source_paths, CHECKS.keys())
    state = {"dossier_path": args.dossier, "source_paths": source_paths, "flags": []}

    try:
        app = build_graph(interactive=args.review)
        cfg = {"configurable": {"thread_id": run_id}}
        final = app.invoke(state, cfg) if args.review else app.invoke(state)
        flags = final.get("adjudicated_flags", [])
        if args.review:
            _interactive_review(app, cfg, flags, args.reviewer, audit, input_fn)
            final = app.invoke(None, cfg)
    except Exception as exc:  # noqa: BLE001 - record the failure in the ledger, then surface it
        log.exception("run failed")
        audit.run_failed(f"{type(exc).__name__}: {exc}")
        print(f"error: run failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3

    flags = final.get("adjudicated_flags", [])
    report = final.get("report", {})
    audit.ingested(len(final.get("source_facts", [])), len(source_paths))
    audit.claims_extracted(len(final.get("claims", [])))
    for f in flags:
        audit.flag_raised(f)
    audit.run_completed(report)

    print("FLAGS")
    for f in flags:
        print(f"  [{f.severity.value.upper():8}] {f.check_name}: {f.message}")
    print("\nDISCREPANCY REPORT")
    print(json.dumps(report, indent=2))

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(flags_to_json(report, flags), indent=2), encoding="utf-8")
    if args.sarif:
        Path(args.sarif).write_text(json.dumps(flags_to_sarif(flags, PIPELINE_VERSION), indent=2),
                                    encoding="utf-8")
    if args.report:
        from .report import render_html_report
        Path(args.report).write_text(render_html_report(report, flags), encoding="utf-8")
        print(f"\nWrote HTML report to {args.report}")
    print(f"Audit trail appended to {audit.path} (run_id {run_id})")

    if args.fail_on != "none":
        threshold = severity_rank(args.fail_on)
        if any(severity_rank(f.severity) >= threshold for f in flags):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
