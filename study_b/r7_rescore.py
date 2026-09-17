#!/usr/bin/env python
"""R7 durability: rescore the 1,450 LAMP-rewritten test posts with the frozen
stage-5 instrument (artifacts/METHODOLOGY.md stage 6).

Reuses study_b.r5_apply verbatim (PROMPT, feature loading, Applier, model
gemini-3.6-flash with minimal thinking, aspect-based application, single-select
forcing). The ONLY difference from the stage-5 full run is the input documents:
the rewritten texts from outputs/study_b/r7/rewritten_{model}.jsonl instead of
the frozen corpus. Prompting and generation config are byte-identical.

Resume-safe: one JSONL row per (doc_id, source, dim) into
outputs/study_b/r7/answers_rewritten.jsonl; reruns skip completed keys.

  .venv/bin/python -m study_b.r7_rescore [--limit-docs N] [--max-usd 60]
"""
import argparse
import concurrent.futures as cf
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from study_b.r5_apply import Applier, load_features  # noqa: E402

R7 = Path("outputs/study_b/r7")
MODELS = ["gpt", "claude", "gemini", "deepseek", "kimi"]
TAG = "rewritten"


def iter_rewritten(limit_docs: int | None = None):
    n = 0
    for m in MODELS:
        for line in open(R7 / f"rewritten_{m}.jsonl"):
            r = json.loads(line)
            yield {"doc_id": r["doc_id"], "source": r["source"],
                   "text": r["rewritten_text"]}
            n += 1
            if limit_docs and n >= limit_docs:
                return


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit-docs", type=int, default=None,
                    help="pilot: only first N rewritten docs")
    ap.add_argument("--concurrency", type=int, default=16)
    ap.add_argument("--max-usd", type=float, default=60.0)
    args = ap.parse_args()

    by_dim = load_features()
    n_feats = sum(len(v) for v in by_dim.values())
    print(f"taxonomy: {n_feats} features across {len(by_dim)} dims",
          file=sys.stderr)

    texts = list(iter_rewritten(args.limit_docs))
    print(f"texts: {len(texts)}", file=sys.stderr)

    units = [(t, dim, feats) for t in texts
             for dim, feats in sorted(by_dim.items())]

    outfile = R7 / f"answers_{TAG}.jsonl"
    done = set()
    if outfile.exists():
        for l in open(outfile):
            r = json.loads(l)
            if "answers" in r:
                done.add((r["doc_id"], r["source"], r["dim"]))
    todo = [u for u in units
            if (u[0]["doc_id"], u[0]["source"], u[1]) not in done]
    print(f"calls: {len(todo)} to run ({len(done)} done)", file=sys.stderr)

    app = Applier()
    n_ok = n_err = 0
    t0 = time.time()
    with open(outfile, "a") as fh, cf.ThreadPoolExecutor(args.concurrency) as ex:
        for i, rec in enumerate(
                ex.map(lambda u: app.call(u[0], u[1], u[2], TAG), todo), 1):
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            n_ok += "answers" in rec
            n_err += "error" in rec
            if i % 200 == 0:
                rate = i / max(1, time.time() - t0) * 3600
                print(f"  [{i}/{len(todo)}] ok={n_ok} err={n_err} "
                      f"spent=${app.spent:.2f} rate={rate:.0f}/h",
                      file=sys.stderr)
            if app.spent > args.max_usd:
                print(f"STOPPED: spend cap ${args.max_usd}", file=sys.stderr)
                return 1
    print(f"done tag={TAG}: {n_ok} ok, {n_err} failed (rerun to retry), "
          f"spend ${app.spent:.2f}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
