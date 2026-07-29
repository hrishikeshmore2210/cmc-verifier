"""Claim extraction from the dossier (ARCHITECTURE.md §2.3).

PHASE 0 version: the dossier is structured JSON, one record per claim. Real
narrative parsing (LLM extraction of atomic claims from Module 3 prose) is a
later step; the output contract (list[Claim]) does not change.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..models import Claim, VerificationState


def extract_claims(state: VerificationState) -> VerificationState:
    dossier_path = state["dossier_path"]
    rows = json.loads(Path(dossier_path).read_text())
    claims = [Claim(**row) for row in rows]
    print(f"[extract_claims] parsed {len(claims)} claim(s) from {dossier_path}")
    return {"claims": claims}