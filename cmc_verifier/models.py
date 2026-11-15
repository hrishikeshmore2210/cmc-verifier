"""Domain models + graph state.

Design invariant (see ARCHITECTURE.md §0.2): no value or flag exists without a
SourceRef pointing back to where it came from. Keep it that way.

The fact records are deliberately *generation-ready*, not just comparison-ready
(ARCHITECTURE.md §2.2). Do not collapse them into "just a mismatch" shape — that
seam is what lets the phase-2 author module bolt on without a rewrite.
"""

from __future__ import annotations

import operator
from enum import Enum
from typing import Annotated, Any, Literal, Optional, TypedDict

from pydantic import BaseModel, Field


class Severity(str, Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


class SourceRef(BaseModel):
    """Where a value physically came from. The provenance invariant."""
    document_id: str
    page: Optional[int] = None
    location: Optional[str] = None  # bbox / cell / anchor within the page


class SourceFact(BaseModel):
    """A structured, generation-ready CMC fact extracted from source data."""
    analyte: Optional[str] = None
    method: Optional[str] = None
    result: Optional[float] = None
    qualifier: Optional[Literal["<", ">", "<=", ">="]] = None   # for limit results
    result_text: Optional[str] = None      # non-numeric result, e.g. "ND" (not detected)
    unit: Optional[str] = None
    spec_limit: Optional[str] = None
    batch_id: Optional[str] = None
    date: Optional[str] = None
    source_ref: SourceRef


class Claim(BaseModel):
    """An atomic, checkable assertion parsed from the dossier narrative."""
    text_span: str
    ctd_section: str                       # e.g. "3.2.P.5.1"
    claim_type: Literal["quantitative", "descriptive"]
    analyte: Optional[str] = None          # matching key for grounding
    batch_id: Optional[str] = None         # matching key for grounding
    quantitative_value: Optional[float] = None
    qualifier: Optional[Literal["<", ">", "<=", ">="]] = None   # carried from the dossier
    result_text: Optional[str] = None      # non-numeric claim, e.g. "ND"
    linked_source_ref: Optional[SourceRef] = None   # None => ungrounded (flag it)

class Flag(BaseModel):
    """A discrepancy the human will adjudicate. The system never resolves it."""
    check_name: str
    severity: Severity
    message: str
    dossier_ref: Optional[str] = None      # section / span the claim lives in
    source_ref: Optional[SourceRef] = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    rationale: str = ""


class VerificationState(TypedDict, total=False):
    """LangGraph state. Only `flags` has a reducer because the parallel check
    nodes all write to it concurrently; everything else has a single writer."""
    dossier_path: str
    source_paths: list[str]
    source_facts: list[SourceFact]         # written by: ingest
    claims: list[Claim]                    # written by: extract_claims
    links: list[dict[str, Any]]            # written by: ground
    flags: Annotated[list[Flag], operator.add]   # written by: check_* (parallel)
    adjudicated_flags: list[Flag]          # written by: critic
    report: dict[str, Any]                 # written by: critic / review
    decisions: list[dict[str, Any]]        # written by: the human reviewer (via update_state)
