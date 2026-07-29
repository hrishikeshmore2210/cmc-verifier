# CMC Dossier Verification Engine — Architecture & Build Spec

**Working name:** (TBD)
**Thesis:** A source-grounded, multi-agent system that verifies CMC (Chemistry, Manufacturing & Controls) documentation against its underlying data — flagging discrepancies for a human to adjudicate — and is architected so that *authoring* becomes an additive module rather than a rebuild.

**Positioning in one line:** We don't decide, and we don't (yet) write. We catch the errors that turn into deficiency letters, and we prove every flag against a source.

---

## 0. Design principles (these constrain every decision below)

1. **Flag, never decide.** The system surfaces discrepancies with evidence; a qualified human adjudicates. This keeps *model influence* low, which is what makes the tool cheap for a regulated buyer to validate.
2. **No ungrounded claim, ever.** Every extracted value and every flag carries a pointer to its source (document → page → location). This is an architectural invariant, enforced in code — not a prompt instruction.
3. **Reproducible by construction.** Same input → same output. Pinned model versions, temperature 0 on reasoning steps, cached extractions, deterministic checks in code wherever possible.
4. **The audit trail is the architecture, not a feature.** Model the whole system as an append-only event log (event sourcing). Every extraction, check, model version, and human decision is an immutable event. 21 CFR Part 11 / Annex 11 traceability then falls out for free instead of being retrofitted.
5. **Model the data bidirectionally.** Represent CMC facts as a structured source-of-truth that maps *both* ways to narrative text. Verification reads narrative→source; authoring reads source→narrative. Get this shape right now and authoring is additive; get it wrong and you rebuild.

---

## 1. System overview

Two graphs that must reconcile:

- **Source Data Graph** — structured facts extracted from CoAs, batch records, stability tables, specifications, method reports.
- **Dossier Claims Graph** — atomic, checkable claims parsed out of the Module 3 narrative, each tagged to its CTD section.

The engine links claims to source facts, runs a battery of check agents over the linked (and unlinked) pairs, and a critic layer adjudicates and scores each flag before a human sees it.

```
            ┌─────────────────────── SHARED SPINE ───────────────────────┐
 sources ──▶│ Ingestion & Normalization ──▶ Canonical Data Model (SoT) ──┐│
 dossier ──▶│ Claim Extraction ──────────────────────────────────────┐  ││
            │                        Retrieval / Grounding ◀──────────┴──┘│
            └───────────────────────────────┬─────────────────────────────┘
                                             ▼
                        ┌──────────── VERIFY (v1) ────────────┐
                        │  parallel Check Agents (LangGraph)  │
                        │  ▶ numerical reconciliation         │
                        │  ▶ spec-vs-result                   │
                        │  ▶ cross-section consistency        │
                        │  ▶ unit / nomenclature              │
                        │  ▶ completeness (CTD structure)     │
                        │  ▶ traceability (ungrounded claims) │
                        │  ▶ stability trend                  │
                        └──────────────┬──────────────────────┘
                                       ▼
                        Critic / Adjudication (severity + rationale + confidence)
                                       ▼
                        Human-in-the-loop Review  ──▶ immutable decision log
                                       ▼
                        ┌──── AUTHOR (phase 2, additive) ────┐
                        │ source→narrative generation, then  │
                        │ the SAME verifier runs on its own  │
                        │ output before a human sees it      │
                        └────────────────────────────────────┘
```

---

## 2. The shared spine (BUILD NOW — this is the moat)

### 2.1 Ingestion & Normalization
The unglamorous, defensible core. Parsing messy CDMO batch records and CoA PDFs into structured, reconcilable data is genuinely hard, and it's what a pure-LLM competitor would have to rebuild.

Components:
- **Document classifier** — what is this? (CoA, batch record, stability table, specification, method validation report, dossier section).
- **Layout-aware extraction** — tables and key-value pairs. Start with a structured extractor (e.g. Docling / `unstructured`); fall back to a vision model for scanned or ugly CoAs.
- **Measurement/entity extraction** into a canonical schema: `{analyte, method, result, unit, spec_limit, batch_id, date, source_ref}`.
- **Unit normalization & nomenclature resolution** — unit conversion, synonym mapping, salt-vs-free-base, analyte aliasing. Maintain a controlled vocabulary you can extend per product.
- **Provenance capture** — every extracted value keeps `document_id + page + location` (bounding box if available). Non-negotiable.

> **Seam for later:** keep extraction *modality-scoped*. Ship small-molecule Module 3 (drug product) first; leave the schema open for biologics later, don't generalize prematurely.

### 2.2 Canonical Data Model (Source of Truth)
Typed (Pydantic) domain model, persisted in Postgres (+ object store for the raw source docs). Represents specifications, batch analytical results, stability data points, process parameters, and materials. Also holds the dossier narrative parsed into CTD subsections (3.2.S.*, 3.2.P.*).

Design the fact records so they are *generation-ready*, not just *comparison-ready* — a fact should carry enough structure that authoring could later render it into prose. This is the single most important seam in the whole system.

### 2.3 Claim Extraction (from the dossier)
Parse the narrative into atomic claims, each `{text_span, ctd_section, claim_type, quantitative_value?, linked_source_ref?}`. Example: *"The assay result for batch X was 99.2%"* → a quantitative claim that should resolve to a CoA record.

### 2.4 Retrieval / Grounding
Hybrid: **structured lookup** by batch/analyte/date for the numerical spine, **semantic retrieval** (pgvector) for narrative claims that don't key cleanly. Output is a set of `(claim, candidate_source_facts, link_confidence)` tuples that feed the check agents.

---

## 3. Verification layer (BUILD NOW — v1 product)

A set of **check agents** orchestrated in LangGraph. Design each as *deterministic-in-code where possible, LLM-reasoning only where necessary*. The LLM's job is linking and explaining, not arithmetic.

| Check agent | What it catches | Mostly code or LLM? |
|---|---|---|
| **Numerical reconciliation** | Narrative numbers that don't match source within tolerance | Code (once linked) |
| **Spec-vs-result** | Reported results outside the specification stated elsewhere | Code |
| **Cross-section consistency** | Same fact stated differently across sections (e.g. batch formula in 3.2.P.1 vs 3.2.P.3.2) | LLM-assisted |
| **Unit / nomenclature** | Unit drift, analyte naming, salt/base inconsistency | Code + vocab |
| **Completeness / structure** | Missing required CTD elements | Rule-based |
| **Traceability** | Quantitative claims with no linked source (ungrounded) | Code |
| **Stability trend** | Narrative trend doesn't match the data; unreasonable extrapolation | LLM-assisted |

### 3.1 LangGraph shape
- A **state object** carrying the linked claim/fact pairs, accumulated flags, and run metadata.
- **Fan-out** to check agents in parallel (they're independent).
- **Fan-in** to the critic node.
- A **human-in-the-loop interrupt** after the critic, before anything is finalized.
- Every node emits events to the audit log (see §5).

### 3.2 Critic / Adjudication layer
A verifier/critic agent that:
- Reviews each raw flag for validity (kills false positives — the thing that destroys trust fastest).
- Assigns **severity**: critical / major / minor.
- Produces a **rationale with source citations** (side-by-side: dossier text vs source value).
- Attaches a **confidence score**; low-confidence items are routed to the human explicitly rather than suppressed.

The critic *never resolves* a discrepancy — it characterizes it. Resolution is the human's.

---

## 4. Human-in-the-loop review (BUILD NOW — thin but real)

- Discrepancy report: each flag shows source-vs-dossier side by side, severity, rationale, and one-click **accept / dismiss / needs-info**.
- Every human action writes an immutable decision event (who, what, when, why).
- Keep the UI deliberately thin in v1 — the value is the flags and the evidence, not the chrome.

---

## 5. GxP spine (BUILD NOW as seams; harden before first paying customer)

These are cross-cutting and cheap to build in early, expensive to retrofit.

- **Event-sourced audit trail.** Model every state change as an append-only event. This *is* your Part 11 / Annex 11 audit trail, and it makes runs perfectly reconstructable.
- **Versioning & lineage.** Document versions, data versions, **model/prompt versions**. Every flag is attributable to the exact model+prompt+data that produced it.
- **Determinism.** Temperature 0 on reasoning steps, pinned model versions, cached extractions. Regulators want reproducibility; so do you when debugging.
- **Eval harness = validation credibility.** A golden set of dossiers with known injected errors, measured precision/recall per check category. This is not just testing — it *is* the evidence a buyer's risk-based credibility assessment needs, and it maps directly onto the "context of use → risk → credibility evidence" framework regulators now expect for AI in submissions.
- **Citation-grounding guardrail.** A hard rule: no output claim without a source pointer. Ungrounded generations are blocked or flagged, not shown as fact.

> **Why this order:** validation-readiness is a *selling point* in an early market where most firms have no AI-validation plan yet. Build the seams now; write the formal validation pack (URS, quality agreement, SOC 2, change-control release notes, data-return-on-termination) when you have your first design partner asking for it.

---

## 6. MCP integration seams (BUILD ONE NOW, seam the rest)

Agents pull source data and drafts through **MCP tools**, read-only to start.

- **Build now:** a local filesystem / simple document-store MCP server so the whole pipeline runs end-to-end on real files.
- **Seam for later:** connectors to eDMS/data platforms (Veeva Vault, SharePoint/Documentum, LIMS). Design the tool interface so swapping the backing store doesn't touch the agents.

This is also your clean portfolio demonstration of MCP tool integration — keep the tool contracts narrow and typed.

---

## 7. Authoring module (PHASE 2 — leave seams, do not build yet)

The payoff of the shared spine. Because the canonical data model is generation-ready (§2.2):

- An **author agent** drafts section narrative *from structured source facts*, each sentence grounded in a source record.
- Then **the existing verifier runs on the author's own output** before any human sees it — self-checking authoring.

That last point is the differentiated pitch a pure-authoring incumbent can't easily copy: *the same engine that catches errors writes the draft, then re-checks itself against source.* You expand into authoring **inside accounts that already trust your checker** — a warm upsell, not a cold black-box sell.

**Seams to leave now (so phase 2 is additive):**
1. Fact records carry enough structure to render to prose.
2. The verifier is callable as a library on arbitrary narrative — including narrative your own author produced.
3. Citation-grounding guardrail already treats "generated text" and "human text" identically.

---

## 8. Suggested stack

| Concern | Choice | Notes |
|---|---|---|
| Orchestration | **LangGraph** | State graph: spine nodes → parallel checks → critic → HITL interrupt |
| Extraction | Docling / `unstructured`, vision-LLM fallback | Table-heavy CoAs are the hard case |
| Domain model | **Pydantic** | Typed facts; validation at the boundary |
| Storage | Postgres + **pgvector** + object store | Structured facts + semantic retrieval + raw docs |
| Reasoning model | Strong reasoning model, temp 0 | For linking, critic, stability reasoning |
| Deterministic checks | Plain Python | Arithmetic and spec bounds never touch an LLM |
| Tracing / eval | LangSmith or promptfoo + custom golden-set harness | Traces double as audit evidence |
| Audit | Append-only event log (event sourcing) | Part 11-shaped by construction |

---

## 9. Build roadmap

**Phase 0 — Golden dataset (do this first; nothing works without it).**
Assemble example Module 3 content from public assessment reports / ICH examples, plus **synthetic error injection** (perturb known-good dossiers with realistic discrepancies). This is your known-answer set and your validation evidence.

**Phase 1 — Vertical slice.**
Ingestion + canonical model + **numerical reconciliation** (the single highest-value check), end-to-end, on **one modality** (small-molecule drug product, Module 3). Prove the spine on real files via the local MCP server.

**Phase 2 — Full verifier.**
Add remaining check agents + critic (severity, rationale, confidence) + review report. Wire the eval harness to report precision/recall per check.

**Phase 3 — GxP hardening.**
Audit trail formalization, versioning/lineage, first validation documentation pack. Do this when a design partner is in sight, not before.

**Phase 4 — Authoring.**
Source→narrative generation with self-verification. Expand within trusting accounts.

---

## 10. Why this is a worthy flagship (portfolio framing)

Even pre-revenue, this project demonstrates, concretely:
- **Multi-agent orchestration** (LangGraph state graph, parallel check agents, critic, HITL interrupts).
- **MCP tool integration** with clean, typed contracts.
- **RAG with provenance** — hybrid structured + semantic retrieval where every output is source-linked.
- **Eval-driven development** — golden set, injected errors, precision/recall per capability.
- **Regulated-AI judgment** — reproducibility, audit-by-design, low-model-influence positioning.

That's a portfolio that argues you can build trustworthy agentic systems in a domain where "trustworthy" is the entire job — which is exactly what serious AI-engineering roles are screening for.

---

## Open decisions to resolve next
- Confirm **first modality** (small-molecule Module 3 drug product is the recommended default).
- Pick the **golden-dataset sources** and the error-injection taxonomy.
- Decide the **v1 check set** to ship first (recommend: numerical reconciliation + spec-vs-result + traceability — the three that are mostly deterministic and highest-trust).
- Choose the **local MCP store** shape so it mirrors a future Vault/SharePoint swap.
