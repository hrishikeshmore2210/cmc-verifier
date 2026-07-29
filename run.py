"""Entrypoint. Run from the repo root:

    python run.py                 # print flags + JSON report
    python run.py --report        # also write report.html
    python run.py --report out.html

Builds the graph and runs it on the golden dataset in data/sample/.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cmc_verifier import build_graph
from cmc_verifier.mcp_store import LocalDocumentStore

SAMPLE_DIR = Path(__file__).parent / "data" / "sample"
SOURCES_DIR = SAMPLE_DIR / "sources"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the CMC verification pipeline.")
    parser.add_argument("--report", nargs="?", const="report.html", default=None,
                        help="also write an HTML discrepancy report (default: report.html)")
    args = parser.parse_args()

    store = LocalDocumentStore(SOURCES_DIR)
    source_paths = [str(p) for p in store.list_documents()
                    if p.suffix.lower() in {".csv", ".pdf", ".json"}
                    and not p.name.endswith(".expected.json")]

    initial_state = {
        "dossier_path": str(SAMPLE_DIR / "dossier.json"),
        "source_paths": source_paths,
        "flags": [],
    }

    app = build_graph()
    print("\n--- running verification pipeline ---")
    final_state = app.invoke(initial_state)
    print("--- done ---\n")

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


if __name__ == "__main__":
    main()