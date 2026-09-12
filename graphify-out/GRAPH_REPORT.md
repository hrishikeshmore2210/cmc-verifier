# Graph Report - cmc-verifier  (2026-09-12)

## Corpus Check
- Corpus is ~12,593 words - fits in a single context window. You may not need a graph.

## Summary
- 275 nodes · 512 edges · 16 communities (13 shown, 2 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 56 edges (avg confidence: 0.91)
- Token cost: 188,643 input · 0 output

## Community Hubs (Navigation)
- Architecture & Design Docs
- Verification Check Logic
- Data Extraction & Adapters
- LangGraph Pipeline Nodes
- Audit Trail & Logging
- MCP Store & Entry Point
- HTML Report Rendering
- CoA Batch Test Data
- PDF CoA Extraction
- Numerical Reconciliation Logic
- Discrepancy Report Screenshot
- Eval Harness & Golden Dataset
- GxP Hardening & Audit Design
- Borderless PDF Generator Script
- Sample PDF Generator Script

## God Nodes (most connected - your core abstractions)
1. `VerificationState` - 21 edges
2. `AuditLog` - 17 edges
3. `Severity` - 14 edges
4. `CMC Verifier (project)` - 14 edges
5. `parse_coa_csv()` - 12 edges
6. `parse_coa_pdf()` - 12 edges
7. `build_graph()` - 12 edges
8. `Flag` - 12 edges
9. `SourceRef` - 11 edges
10. `Parallel Check Agents (LangGraph)` - 11 edges

## Surprising Connections (you probably didn't know these)
- `test_flag_raised_captures_provenance()` --uses--> `Severity`  [INFERRED]
  tests/test_audit.py → cmc_verifier/models.py
- `_flags()` --uses--> `Severity`  [INFERRED]
  tests/test_report.py → cmc_verifier/models.py
- `langgraph (dependency)` --conceptually_related_to--> `Determinism (temp 0, pinned versions)`  [AMBIGUOUS]
  requirements.txt → ARCHITECTURE.md
- `test_measurement_parsing_edge_cases()` --calls--> `parse_measurement()`  [EXTRACTED]
  tests/test_extraction_adversarial.py → cmc_verifier/adapters.py
- `test_parse_value_strips_units()` --calls--> `parse_value()`  [EXTRACTED]
  tests/test_extraction.py → cmc_verifier/adapters.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Parallel Check Agent Fan-out** — architecture_numerical_reconciliation, architecture_spec_vs_result, architecture_cross_section_consistency, architecture_unit_nomenclature_check, architecture_completeness_structure, architecture_traceability_check, architecture_stability_trend_check [EXTRACTED 1.00]
- **Core Design Principles (§0)** — architecture_flag_never_decide, architecture_no_ungrounded_claim, architecture_reproducible_by_construction, architecture_audit_trail_as_architecture, architecture_bidirectional_data_model [EXTRACTED 1.00]
- **GxP Spine Components (§5)** — architecture_event_sourced_audit_trail, architecture_versioning_lineage, architecture_determinism, architecture_eval_harness, architecture_citation_grounding_guardrail [EXTRACTED 1.00]
- **Discrepancy Report Layout Structure** — docs_report_png, docs_report_summary_counts, docs_report_critical_section, docs_report_major_section [EXTRACTED 1.00]
- **Major Discrepancy Check Types** — docs_report_major_section, docs_report_cross_section_consistency, docs_report_numerical_reconciliation [EXTRACTED 1.00]

## Communities (16 total, 2 thin omitted)

### Community 0 - "Architecture & Design Docs"
Cohesion: 0.05
Nodes (57): Author agent (source→narrative generation), Authoring module (phase 2, additive), Model the data bidirectionally (design principle), Canonical Data Model (Source of Truth), Parallel Check Agents (LangGraph), Citation-grounding guardrail, Claim Extraction, Completeness / structure (CTD) check (+49 more)

### Community 1 - "Verification Check Logic"
Cohesion: 0.11
Nodes (31): BaseModel, Flag, A discrepancy the human will adjudicate. The system never resolves it., Severity, check_cross_section_consistency(), check_numerical_reconciliation(), check_spec_vs_result(), check_traceability() (+23 more)

### Community 2 - "Data Extraction & Adapters"
Cohesion: 0.10
Nodes (31): canonical_analyte(), _clean(), _extract_table_rows(), facts_from_rows(), _has_header(), parse_coa_csv(), parse_measurement(), parse_value() (+23 more)

### Community 3 - "LangGraph Pipeline Nodes"
Cohesion: 0.14
Nodes (22): build_graph(), Assemble the verification graph (ARCHITECTURE.md §1, §3.1). Flow: START ->…, Claim, Domain models + graph state. Design invariant (see ARCHITECTURE.md §0.2): no…, A structured, generation-ready CMC fact extracted from source data., An atomic, checkable assertion parsed from the dossier narrative., LangGraph state. Only `flags` has a reducer because the parallel check nodes…, SourceFact (+14 more)

### Community 4 - "Audit Trail & Logging"
Cohesion: 0.16
Nodes (15): AuditLog, _canonical(), _hash_record(), Append-only, tamper-evident audit trail (ARCHITECTURE.md §5). GxP data-…, Return (ok, problems). Recompute each event's hash and check the chain., Deterministic serialization for hashing (the 'hash' field is excluded)., Writes immutable, hash-chained events to a JSONL ledger (append-only)., verify_audit_log() (+7 more)

### Community 5 - "MCP Store & Entry Point"
Cohesion: 0.20
Nodes (10): LocalDocumentStore, Path, Local filesystem "MCP store" — the build-now seam (ARCHITECTURE.md §6). Right…, main(), Entrypoint. Run from the repo root: python run.py # run pipeline, print flags +…, Eval harness (ARCHITECTURE.md §5). Runs the pipeline on the Phase 0 golden…, _run(), test_check_flag_counts() (+2 more)

### Community 6 - "HTML Report Rendering"
Cohesion: 0.25
Nodes (14): Where a value physically came from. The provenance invariant., SourceRef, _esc(), _flag_card(), HTML discrepancy report renderer (ARCHITECTURE.md §4). Turns adjudicated flags…, render_html_report(), _sev_value(), _source_ref_str() (+6 more)

### Community 7 - "CoA Batch Test Data"
Cohesion: 0.19
Nodes (14): Acme Tablets 10 mg (Product), Assay = 100.1% (HPLC), Batch B-007 (Acme Tablets 10 mg, Mfg 10-Apr-2026), HPLC (High Performance Liquid Chromatography), KF (Karl Fischer titration), Related Substances - Total = 0.28% (HPLC), Water Content = 2.9% (KF), Acme Tablets 10 mg (Product) (+6 more)

### Community 8 - "PDF CoA Extraction"
Cohesion: 0.24
Nodes (11): parse_coa_pdf(), PDF adapter (ARCHITECTURE.md §2.1). Its ONLY new job vs CSV: turn a PDF into…, _key(), Borderless-PDF extraction eval (ARCHITECTURE.md §5). The hard case: a table…, test_borderless_batch_captured(), test_borderless_extraction_matches_ground_truth(), _key(), PDF extraction eval (ARCHITECTURE.md §5). Proves the PDF adapter recovers the… (+3 more)

### Community 9 - "Numerical Reconciliation Logic"
Cohesion: 0.39
Nodes (10): Compare a dossier claim measurement to a source fact measurement. Returns None…, reconcile_measurement(), C(), F(), Unit tests for measurement reconciliation (ARCHITECTURE.md §3). The truth table…, test_matching_values_no_flag(), test_qualifier_mismatch_flags(), test_result_type_mismatch_flags() (+2 more)

### Community 10 - "Discrepancy Report Screenshot"
Cohesion: 0.38
Nodes (7): Critical Discrepancies Section, cross_section_consistency check type, Major Discrepancies Section, numerical_reconciliation check type, CMC Verification Discrepancy Report (Screenshot), spec_vs_result verdict type (spec violation checks), Discrepancy Summary Counts (9 total: Critical 3, Major 6, Minor 0)

### Community 11 - "Eval Harness & Golden Dataset"
Cohesion: 0.40
Nodes (6): Eval harness (golden set, precision/recall), Phase 0 — Golden dataset, Tracing / eval tooling (LangSmith or promptfoo), Eval suite (34 pytest tests), Golden dataset (synthetic, injected errors), pytest (dependency)

### Community 12 - "GxP Hardening & Audit Design"
Cohesion: 0.50
Nodes (4): The audit trail is the architecture, not a feature (design principle), Event-sourced audit trail, Phase 3 — GxP hardening, Versioning & lineage

## Ambiguous Edges - Review These
- `Authoring module (phase 2, additive)` → `Phase 4 — Authoring`  [AMBIGUOUS]
  ARCHITECTURE.md · relation: conceptually_related_to
- `Determinism (temp 0, pinned versions)` → `langgraph (dependency)`  [AMBIGUOUS]
  requirements.txt · relation: conceptually_related_to

## Knowledge Gaps
- **21 isolated node(s):** `Document classifier`, `Unit normalization & nomenclature resolution`, `Versioning & lineage`, `MCP integration seams`, `Author agent (source→narrative generation)` (+16 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 76 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `Authoring module (phase 2, additive)` and `Phase 4 — Authoring`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Determinism (temp 0, pinned versions)` and `langgraph (dependency)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `SourceRef` connect `HTML Report Rendering` to `Verification Check Logic`, `Data Extraction & Adapters`, `LangGraph Pipeline Nodes`, `Audit Trail & Logging`, `Numerical Reconciliation Logic`?**
  _High betweenness centrality (0.050) - this node is a cross-community bridge._
- **Why does `AuditLog` connect `Audit Trail & Logging` to `MCP Store & Entry Point`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **Why does `VerificationState` connect `LangGraph Pipeline Nodes` to `Verification Check Logic`?**
  _High betweenness centrality (0.040) - this node is a cross-community bridge._
- **Are the 11 inferred relationships involving `VerificationState` (e.g. with `build_graph()` and `check_cross_section_consistency()`) actually correct?**
  _`VerificationState` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `Severity` (e.g. with `check_cross_section_consistency()` and `check_numerical_reconciliation()`) actually correct?**
  _`Severity` has 7 INFERRED edges - model-reasoned connections that need verification._