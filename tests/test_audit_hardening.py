import json
import threading

import pytest

from cmc_verifier.audit import AuditLog, verify_audit_log
from cmc_verifier.mcp_store import DocumentAccessError, LocalDocumentStore


def _complete_log(path, run_id="r1"):
    log = AuditLog(path, run_id=run_id)
    log.run_completed({"total_flags": 0})
    return log


def test_valid_log_verifies(tmp_path):
    p = tmp_path / "a.jsonl"
    _complete_log(p)
    assert verify_audit_log(p) == (True, [])


def test_tampering_detected(tmp_path):
    p = tmp_path / "a.jsonl"
    _complete_log(p)
    p.write_text(p.read_text(encoding="utf-8").replace('"total_flags": 0', '"total_flags": 9'), encoding="utf-8")
    ok, problems = verify_audit_log(p)
    assert not ok and any("altered" in x for x in problems)


def test_malformed_line_reported_not_raised(tmp_path):
    p = tmp_path / "a.jsonl"
    _complete_log(p)
    with p.open("a", encoding="utf-8") as fh:
        fh.write("{garbage\n")
    ok, problems = verify_audit_log(p)
    assert not ok and any("malformed" in x for x in problems)


def test_truncated_tail_reported(tmp_path):
    p = tmp_path / "a.jsonl"
    log = AuditLog(p, run_id="r1")
    log.run_started(p, [], ["c"])
    log.run_completed({})
    lines = p.read_text(encoding="utf-8").splitlines()
    p.write_text(lines[0] + "\n", encoding="utf-8")        # drop run_completed
    ok, problems = verify_audit_log(p)
    assert not ok and any("truncation" in x for x in problems)


def test_hmac_detects_rewritten_chain(tmp_path, monkeypatch):
    monkeypatch.setenv("AUDIT_HMAC_KEY", "secret")
    p = tmp_path / "a.jsonl"
    _complete_log(p)
    assert verify_audit_log(p)[0]
    monkeypatch.setenv("AUDIT_HMAC_KEY", "other-key")      # forger lacks the real key
    ok, problems = verify_audit_log(p)
    assert not ok and any("HMAC" in x for x in problems)


def test_run_started_records_input_hashes(tmp_path):
    src = tmp_path / "s.csv"
    src.write_text("x", encoding="utf-8")
    rec = AuditLog(tmp_path / "a.jsonl").run_started(src, [src], [])
    assert len(rec["input_hashes"][str(src)]) == 64


def test_concurrent_writers_do_not_fork_chain(tmp_path):
    p = tmp_path / "a.jsonl"
    def work(i):
        log = AuditLog(p, run_id=f"r{i}")
        for _ in range(5):
            log.claims_extracted(i)
        log.run_completed({})
    threads = [threading.Thread(target=work, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    seqs = [json.loads(ln)["seq"] for ln in p.read_text(encoding="utf-8").splitlines()]
    assert seqs == list(range(1, 25))
    assert verify_audit_log(p)[0]


def test_store_blocks_traversal_and_symlink(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "ok.txt").write_text("hi", encoding="utf-8")
    secret = tmp_path / "secret.txt"
    secret.write_text("nope", encoding="utf-8")
    store = LocalDocumentStore(root)
    assert store.read("ok.txt") == b"hi"
    with pytest.raises(DocumentAccessError):
        store.read("../secret.txt")
    with pytest.raises(DocumentAccessError):
        store.read(secret)


def test_store_size_limit(tmp_path):
    (tmp_path / "big.bin").write_bytes(b"x" * 100)
    with pytest.raises(DocumentAccessError):
        LocalDocumentStore(tmp_path, max_bytes=10).read("big.bin")
