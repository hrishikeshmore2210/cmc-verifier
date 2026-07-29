# CMC Dossier Verification Engine

A source-grounded, multi-agent system that verifies CMC (Chemistry, Manufacturing
& Controls) documentation against its underlying data — flagging discrepancies for
a human to adjudicate. Architected so that *authoring* becomes an additive phase-2
module rather than a rewrite.

See **[ARCHITECTURE.md](ARCHITECTURE.md)** for the full design, build/seam markers,
and roadmap.

## What's in this scaffold

A runnable-empty LangGraph pipeline:

```
START -> ingest -> extract_claims -> ground
      -> [ 7 check agents, in parallel ]
      -> critic -> human_review -> END
```

Every node is a stub that passes state through, so the whole graph runs
end-to-end and prints an empty discrepancy report. That proves the wiring before
you implement a single node. Fill nodes in the order in `ARCHITECTURE.md §9`.

```
cmc_verifier/
  models.py          # Pydantic domain models + LangGraph state (reducer on `flags`)
  graph.py           # graph assembly: spine -> parallel checks -> critic -> HITL
  mcp_store.py       # local filesystem "MCP store" (the build-now MCP seam)
  nodes/
    ingest.py            # ingestion & normalization  (the moat)
    extract_claims.py    # dossier -> atomic claims
    ground.py            # link claims to source facts
    checks.py            # the 7 check agents (registry the graph fans out over)
    critic.py            # adjudication: severity, rationale, confidence
    review.py            # human-in-the-loop (real interrupt: see graph.py comment)
run.py               # entrypoint
tests/               # smoke test = seed of the eval harness
```

## Setup (by hand)

Requires Python 3.10+.

```bash
# 1. create + activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # macOS/Linux
# .venv\Scripts\Activate.ps1       # Windows PowerShell

# 2. install dependencies
pip install -r requirements.txt

# 3. run the empty pipeline (should print an empty report)
python run.py

# 4. run the smoke test
pytest -q
```

## Where to start building

1. **Phase 0 first — the golden dataset.** Nothing works without a known-answer
   set. Assemble example Module 3 content + inject known errors.
2. **First vertical slice:** `ingest` -> `models` -> `numerical_reconciliation`,
   on one modality (small-molecule drug product).
3. Then the remaining checks, then the critic, then GxP hardening, then authoring.

The three highest-trust checks to implement first are `numerical_reconciliation`,
`spec_vs_result`, and `traceability` — they're mostly deterministic.
