"""Structured-output schema for LLM claim extraction.

The model returns these; nothing it returns is trusted until `validate.py` has
checked each claim against the source text (the provenance invariant).
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ExtractedClaim(BaseModel):
    evidence_quote: str = Field(
        description="The exact, contiguous text copied verbatim from the document that states this claim. "
                    "Do not paraphrase, normalise, or merge sentences.")
    ctd_section: str = Field(description="CTD section the claim sits under, e.g. '3.2.P.5.4'; 'unknown' if none.")
    claim_type: Literal["quantitative", "descriptive"]
    analyte: Optional[str] = Field(default=None, description="Test/analyte name as written, e.g. 'Assay'.")
    batch_id: Optional[str] = Field(default=None, description="Batch identifier as written, e.g. 'B-001'.")
    quantitative_value: Optional[float] = Field(default=None, description="Numeric value, without qualifier or unit.")
    qualifier: Optional[Literal["<", ">", "<=", ">="]] = None
    result_text: Optional[str] = Field(default=None, description="Non-numeric result such as 'ND'.")


class ExtractionResult(BaseModel):
    claims: list[ExtractedClaim]
