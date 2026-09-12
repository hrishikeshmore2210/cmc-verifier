"""Append-only, tamper-evident audit trail (ARCHITECTURE.md §5).

GxP data-integrity posture: every run and finding is recorded as an immutable,
timestamped, sequence-numbered event in a JSONL ledger. Each event carries:
  - prev_hash: the hash of the preceding event (genesis for the first)
  - hash:      SHA-256 over this event's content (which includes prev_hash)
This chains the whole file: editing, reordering, or deleting any record changes a
hash and breaks the link to the next one, which `verify_audit_log` detects.

Events are only ever appended. The chain continues across runs (a new run's first
event links to the last event already on disk), so the entire ledger is one
verifiable sequence.

Verify a log from the command line:
    python -m cmc_verifier.audit audit_log.jsonl
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "1.0"
PIPELINE_VERSION = "0.5.0"          # bump on material change to checks/adapters/format
GENESIS_HASH = "0" * 64


def _canonical(record: dict) -> str:
    """Deterministic serialization for hashing (the 'hash' field is excluded)."""
    payload = {k: v for k, v in record.items() if k != "hash"}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _hash_record(record: dict) -> str:
    return hashlib.sha256(_canonical(record).encode("utf-8")).hexdigest()


class AuditLog:
    """Writes immutable, hash-chained events to a JSONL ledger (append-only)."""

    def __init__(self, path, run_id=None):
        self.path = Path(path)
        self.run_id = run_id or uuid.uuid4().hex[:12]
        self._seq = 0
        self._prev_hash = GENESIS_HASH
        # Continue the chain + sequence from any existing ledger on disk.
        if self.path.exists():
            lines = [ln for ln in self.path.read_text(encoding="utf-8").splitlines() if ln.strip()]
            if lines:
                last = json.loads(lines[-1])
                self._prev_hash = last.get("hash", GENESIS_HASH)
                self._seq = last.get("seq", 0)

    def _emit(self, event_type, payload):
        self._seq += 1
        record = {
            "seq": self._seq,
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "schema_version": SCHEMA_VERSION,
            "pipeline_version": PIPELINE_VERSION,
            "event": event_type,
            "prev_hash": self._prev_hash,
            **payload,
        }
        record["hash"] = _hash_record(record)
        self._prev_hash = record["hash"]
        with self.path.open("a", encoding="utf-8") as fh:      # append-only, never truncate
            fh.write(json.dumps(record, default=str) + "\n")
        return record

    def run_started(self, dossier_path, source_paths, checks):
        return self._emit("run_started", {
            "dossier": str(dossier_path),
            "sources": [str(p) for p in source_paths],
            "checks_enabled": list(checks),
        })

    def ingested(self, fact_count, document_count):
        return self._emit("ingested", {"facts": fact_count, "documents": document_count})

    def claims_extracted(self, claim_count):
        return self._emit("claims_extracted", {"claims": claim_count})

    def flag_raised(self, flag):
        ref = flag.source_ref
        sev = flag.severity.value if hasattr(flag.severity, "value") else str(flag.severity)
        return self._emit("flag_raised", {
            "check": flag.check_name,
            "severity": sev,
            "message": flag.message,
            "dossier_ref": flag.dossier_ref,
            "source_ref": None if ref is None else {
                "document_id": ref.document_id, "page": ref.page, "location": ref.location},
            "confidence": flag.confidence,
        })

    def run_completed(self, report):
        return self._emit("run_completed", {"report": report})


def verify_audit_log(path):
    """Return (ok, problems). Recompute each event's hash and check the chain."""
    path = Path(path)
    problems = []
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    prev = GENESIS_HASH
    for i, line in enumerate(lines, start=1):
        rec = json.loads(line)
        if _hash_record(rec) != rec.get("hash"):
            problems.append(f"line {i} (seq {rec.get('seq')}): content hash mismatch — record was altered")
        if rec.get("prev_hash") != prev:
            problems.append(f"line {i} (seq {rec.get('seq')}): broken chain link — a record was inserted, "
                            f"reordered, or deleted before this one")
        prev = rec.get("hash")
    return (len(problems) == 0, problems)


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "audit_log.jsonl"
    ok, problems = verify_audit_log(target)
    if ok:
        print(f"OK: {target} verified — hash chain intact, no tampering detected.")
    else:
        print(f"FAIL: {target} verification failed:")
        for p in problems:
            print("  -", p)
        sys.exit(1)