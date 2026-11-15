"""Eval harness: per-check precision / recall of flags against a golden answer key.

A flag is identified by (check, analyte, batch). Golden file format:
    [{"check": "...", "analyte": "...", "batch": "..."}, ...]   ("*" = analyte not applicable)

    python -m cmc_verifier.evals                      # sample data, prints a table
    python -m cmc_verifier.evals --min-precision 1 --min-recall 1    # CI gate (exit 1 on regression)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

_CLAIM_RE = re.compile(r"^(?P<analyte>.+?) \((?P<batch>[^)]+)\):")
_BATCH_RE = re.compile(r"^Batch (?P<batch>\S+) ")


def flag_key(flag) -> tuple[str, str, str]:
    """(check, analyte, batch) parsed from a flag message; '?' when not derivable."""
    m = _CLAIM_RE.match(flag.message)
    if m:
        return (flag.check_name, m["analyte"], m["batch"])
    m = _BATCH_RE.match(flag.message)
    if m:
        return (flag.check_name, "*", m["batch"])
    return (flag.check_name, "?", "?")


def score(flags, golden: list[dict]) -> dict[str, dict]:
    """Per-check {tp, fp, fn, precision, recall}. Empty-vs-empty scores 1.0."""
    pred: dict[str, set] = defaultdict(set)
    gold: dict[str, set] = defaultdict(set)
    for f in flags:
        pred[f.check_name].add(flag_key(f))
    for g in golden:
        gold[g["check"]].add((g["check"], g["analyte"], g["batch"]))

    out = {}
    for check in sorted(set(pred) | set(gold)):
        tp = len(pred[check] & gold[check])
        fp = len(pred[check] - gold[check])
        fn = len(gold[check] - pred[check])
        out[check] = {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": tp / (tp + fp) if (tp + fp) else 1.0,
            "recall": tp / (tp + fn) if (tp + fn) else 1.0,
        }
    return out


def failures(scores: dict[str, dict], min_precision: float, min_recall: float) -> list[str]:
    bad = []
    for check, s in scores.items():
        if s["precision"] < min_precision:
            bad.append(f"{check}: precision {s['precision']:.2f} < {min_precision}")
        if s["recall"] < min_recall:
            bad.append(f"{check}: recall {s['recall']:.2f} < {min_recall}")
    return bad


def main(argv=None) -> int:
    from . import build_graph
    from .cli import SAMPLE_DIR, _collect_sources

    p = argparse.ArgumentParser(prog="cmc-eval")
    p.add_argument("--dossier", default=str(SAMPLE_DIR / "dossier.json"))
    p.add_argument("--sources", default=str(SAMPLE_DIR / "sources"))
    p.add_argument("--golden", default=str(SAMPLE_DIR / "golden_flags.json"))
    p.add_argument("--min-precision", type=float, default=1.0)
    p.add_argument("--min-recall", type=float, default=1.0)
    args = p.parse_args(argv)

    golden = json.loads(Path(args.golden).read_text(encoding="utf-8"))
    final = build_graph().invoke({"dossier_path": args.dossier,
                                  "source_paths": _collect_sources(args.sources), "flags": []})
    scores = score(final["adjudicated_flags"], golden)

    print(f"{'check':28} {'tp':>3} {'fp':>3} {'fn':>3} {'precision':>10} {'recall':>7}")
    for check, s in scores.items():
        print(f"{check:28} {s['tp']:>3} {s['fp']:>3} {s['fn']:>3} {s['precision']:>10.2f} {s['recall']:>7.2f}")
    bad = failures(scores, args.min_precision, args.min_recall)
    for b in bad:
        print("FAIL:", b, file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
