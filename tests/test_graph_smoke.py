"""Eval harness (ARCHITECTURE.md §5).

Runs the pipeline on the Phase 0 golden dataset and asserts the known injected
errors are caught. Each new golden case you add becomes another assertion here.
The answer keys live in data/sample/sources/*.expected.json.
"""

from pathlib import Path

from cmc_verifier import build_graph
from cmc_verifier.mcp_store import LocalDocumentStore

SAMPLE_DIR = Path(__file__).parent.parent / "data" / "sample"
SOURCES_DIR = SAMPLE_DIR / "sources"


def _run():
    source_paths = [str(p) for p in LocalDocumentStore(SOURCES_DIR).list_documents()
                    if p.suffix.lower() in {".csv", ".json", ".pdf"}
                    and not p.name.endswith(".expected.json")]
    app = build_graph()
    return app.invoke({
        "dossier_path": str(SAMPLE_DIR / "dossier.json"),
        "source_paths": source_paths,
        "flags": [],
    })


def test_expected_flag_count():
    final = _run()
    assert final["report"]["total_flags"] == 9


def test_check_flag_counts():
    final = _run()
    by_check = final["report"]["by_check"]
    assert by_check.get("numerical_reconciliation") == 4   # + B-009 assay (97.5 vs 99.0)
    assert by_check.get("spec_vs_result") == 3
    assert by_check.get("traceability") == 1
    assert by_check.get("cross_section_consistency") == 1


def test_no_false_positive_on_clean_claims():
    # Assay B-001 (99.2, in spec, grounded) and Water Content B-001 (3.1, in spec,
    # grounded) must NOT be flagged.
    final = _run()
    flagged = {(f.check_name, f.dossier_ref, f.message) for f in final["adjudicated_flags"]}
    assert not any("B-001): reported 99.2" in m for _, _, m in flagged)