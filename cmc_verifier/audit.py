"""Append-only, tamper-evident audit trail (ARCHITECTURE.md §5).

GxP data-integrity posture: every run and finding is recorded as an immutable,
timestamped, sequence-numbered event in a JSONL ledger. Each event carries:
  - prev_hash: the hash of the preceding event (genesis for the first)
  - hash:      SHA-256 over this event's content (which includes prev_hash)
  - hmac:      (optional) HMAC-SHA256 signature, when AUDIT_HMAC_KEY is set
This chains the whole file: editing, reordering, or deleting any record changes a
hash and breaks the link to the next one, which `verify_audit_log` detects. With an
HMAC key, an attacker who can write the file still cannot forge a consistent chain.

Events are only ever appended, under a lock, with the chain tail re-read on every
write, so concurrent runs extend one chain instead of forking it. The chain
continues across runs, so the entire ledger is one verifiable sequence.

Verify a log from the command line:
    python -m cmc_verifier.audit audit_log.jsonl
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "1.0"
PIPELINE_VERSION = "0.5.0"          # bump on material change to checks/adapters/format
GENESIS_HASH = "0" * 64


def _canonical(record: dict) -> str:
    """Deterministic serialization for hashing (hash/hmac fields are excluded)."""
    payload = {k: v for k, v in record.items() if k not in ("hash", "hmac")}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _hash_record(record: dict) -> str:
    return hashlib.sha256(_canonical(record).encode("utf-8")).hexdigest()


def _hmac_key():
    key = os.environ.get("AUDIT_HMAC_KEY")
    return key.encode("utf-8") if key else None


def _sign(record: dict, key: bytes) -> str:
    body = (_canonical(record) + str(record.get("hash", ""))).encode("utf-8")
    return hmac.new(key, body, hashlib.sha256).hexdigest()


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class _FileLock:
    """Cross-platform advisory lock via exclusive lockfile creation."""

    def __init__(self, path: Path, timeout: float = 10.0):
        self.lock_path = Path(str(path) + ".lock")
        self.timeout = timeout

    def __enter__(self):
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                self._fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                return self
            except FileExistsError:
                if time.monotonic() > deadline:
                    raise TimeoutError(f"could not acquire audit lock {self.lock_path}")
                time.sleep(0.05)

    def __exit__(self, *exc):
        os.close(self._fd)
        try:
            os.unlink(self.lock_path)
        except FileNotFoundError:
            pass


class AuditLog:
    """Writes immutable, hash-chained events to a JSONL ledger (append-only)."""

    def __init__(self, path, run_id=None):
        self.path = Path(path)
        self.run_id = run_id or uuid.uuid4().hex[:12]

    def _tail_state(self):
        """(seq, hash) of the last event on disk."""
        if not self.path.exists():
            return 0, GENESIS_HASH
        last = None
        with self.path.open("rb") as fh:
            for line in fh:
                if line.strip():
                    last = line
        if last is None:
            return 0, GENESIS_HASH
        rec = json.loads(last)
        return rec.get("seq", 0), rec.get("hash", GENESIS_HASH)

    def _emit(self, event_type, payload):
        with _FileLock(self.path):
            seq, prev_hash = self._tail_state()
            record = {
                "seq": seq + 1,
                "ts": datetime.now(timezone.utc).isoformat(),
                "run_id": self.run_id,
                "schema_version": SCHEMA_VERSION,
                "pipeline_version": PIPELINE_VERSION,
                "event": event_type,
                "prev_hash": prev_hash,
                **payload,
            }
            record["hash"] = _hash_record(record)
            key = _hmac_key()
            if key:
                record["hmac"] = _sign(record, key)
            with self.path.open("a", encoding="utf-8") as fh:      # append-only, never truncate
                fh.write(json.dumps(record, default=str) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
        return record

    def run_started(self, dossier_path, source_paths, checks):
        """Also records input-file SHA-256s, tying the run to the exact bytes it saw."""
        def digest(p):
            try:
                return sha256_file(p)
            except OSError:
                return None
        return self._emit("run_started", {
            "dossier": str(dossier_path),
            "sources": [str(p) for p in source_paths],
            "input_hashes": {str(p): digest(p) for p in [dossier_path, *source_paths]},
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

    def decision_recorded(self, decision: dict):
        """A human adjudication of one flag (accept / dismiss / needs_info)."""
        return self._emit("decision_recorded", {
            "flag_id": decision["flag_id"],
            "decision": decision["decision"],
            "reviewer": decision["reviewer"],
            "note": decision.get("note", ""),
            "decided_at": decision.get("ts"),
        })

    def run_completed(self, report):
        return self._emit("run_completed", {"report": report})

    def run_failed(self, error: str):
        """Terminal event for a run that crashed, so the ledger never just goes silent."""
        return self._emit("run_failed", {"error": error})


def verify_audit_log(path):
    """Return (ok, problems). Recompute each event's hash and check the chain.

    Malformed lines are reported, not raised. If AUDIT_HMAC_KEY is set, signatures
    are verified too. A log whose final event is not `run_completed` is reported as
    possibly truncated (or a run that crashed).
    """
    path = Path(path)
    problems = []
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    key = _hmac_key()
    prev = GENESIS_HASH
    last_event = None
    for i, line in enumerate(lines, start=1):
        try:
            rec = json.loads(line)
            if not isinstance(rec, dict):
                raise ValueError("not an object")
        except ValueError:
            problems.append(f"line {i}: malformed JSON — record is corrupt")
            prev = None          # chain continuity is unknowable past a corrupt line
            continue
        if _hash_record(rec) != rec.get("hash"):
            problems.append(f"line {i} (seq {rec.get('seq')}): content hash mismatch — record was altered")
        if prev is not None and rec.get("prev_hash") != prev:
            problems.append(f"line {i} (seq {rec.get('seq')}): broken chain link — a record was inserted, "
                            f"reordered, or deleted before this one")
        if key and not hmac.compare_digest(str(rec.get("hmac", "")), _sign(rec, key)):
            problems.append(f"line {i} (seq {rec.get('seq')}): missing or invalid HMAC signature")
        prev = rec.get("hash")
        last_event = rec.get("event")
    if lines and last_event not in ("run_completed", "run_failed"):
        problems.append("log does not end with run_completed/run_failed — possible truncation or an interrupted run")
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
