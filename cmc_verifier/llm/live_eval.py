"""Measure real-model claim-extraction quality against the hand-labelled sample.

    python -m cmc_verifier.llm.live_eval --yes-spend [--no-cache] [--min-precision 1 --min-recall 1]

Makes ONE billed API call (the sample narrative is ~500 tokens in, ~1.5K out; well under
$0.10 on the default model). It refuses to run without --yes-spend. Results are cached,
so re-runs are free unless the model, effort, prompt version, or document changes; use
--no-cache to force a fresh call (e.g. to measure run-to-run variance).

Claims are matched on (section, analyte, batch, value, qualifier, result_text); `score_claims`
is pure and unit-tested offline.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..adapters import canonical_analyte
from ..config import get_settings
from .extractor import ExtractionError, LLMClaimExtractor

SAMPLE = Path(__file__).resolve().parents[2] / "data" / "sample"


def claim_key(c) -> tuple:
    get = (lambda k: c.get(k)) if isinstance(c, dict) else (lambda k: getattr(c, k))
    analyte = get("analyte")
    batch = get("batch_id")
    return (
        get("ctd_section"),
        canonical_analyte(analyte).lower() if analyte else None,
        "".join(ch for ch in batch.lower() if ch.isalnum()) if batch else None,
        get("quantitative_value"),
        get("qualifier"),
        (get("result_text") or None),
    )


def score_claims(predicted, gold) -> dict:
    pred, truth = {claim_key(c) for c in predicted}, {claim_key(c) for c in gold}
    tp, fp, fn = len(pred & truth), len(pred - truth), len(truth - pred)
    return {
        "tp": tp, "fp": fp, "fn": fn,
        "precision": tp / (tp + fp) if (tp + fp) else 1.0,
        "recall": tp / (tp + fn) if (tp + fn) else 1.0,
        "missed": sorted(map(str, truth - pred)),
        "spurious": sorted(map(str, pred - truth)),
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="cmc-llm-eval")
    p.add_argument("--narrative", default=str(SAMPLE / "dossier_narrative.txt"))
    p.add_argument("--gold", default=str(SAMPLE / "dossier.json"))
    p.add_argument("--yes-spend", action="store_true", help="acknowledge that this makes a billed API call")
    p.add_argument("--no-cache", action="store_true", help="ignore and do not write the response cache")
    p.add_argument("--min-precision", type=float, default=1.0)
    p.add_argument("--min-recall", type=float, default=1.0)
    args = p.parse_args(argv)

    if not args.yes_spend:
        print("refusing to run: this makes a billed API call. Re-run with --yes-spend.", file=sys.stderr)
        return 2

    s = get_settings()
    cache_dir = None if args.no_cache else s.llm_cache_dir
    extractor = LLMClaimExtractor(model=s.llm_model, effort=s.llm_effort, cache_dir=cache_dir)
    text = Path(args.narrative).read_text(encoding="utf-8-sig")
    gold = json.loads(Path(args.gold).read_text(encoding="utf-8-sig"))
    try:
        outcome = extractor.extract(text)
    except ExtractionError as exc:
        print(f"extraction failed: {exc}", file=sys.stderr)
        return 3

    r = score_claims(outcome.claims, gold)
    print(f"model={outcome.meta['model']} effort={outcome.meta['effort']} cache_hit={outcome.meta['cache_hit']} "
          f"tokens in/out={outcome.meta.get('input_tokens')}/{outcome.meta.get('output_tokens')}")
    print(f"proposed={outcome.meta['claims_proposed']} rejected_by_validator={outcome.meta['claims_rejected']}")
    print(f"precision={r['precision']:.3f} recall={r['recall']:.3f}  (tp={r['tp']} fp={r['fp']} fn={r['fn']})")
    for label in ("missed", "spurious"):
        for item in r[label]:
            print(f"  {label}: {item}")
    return 0 if (r["precision"] >= args.min_precision and r["recall"] >= args.min_recall) else 1


if __name__ == "__main__":
    sys.exit(main())
