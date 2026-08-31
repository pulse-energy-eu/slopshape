#!/usr/bin/env python
"""R3 input: discovery-pool selection + export into the vendored pipeline layout.

Pool: ~100 docs (~4.3% of the widened corpus), seeded,
stratified by vertical, drawn from story_human_frozen.parquet. The pool list
is committed (provenance) and these doc_ids are EXCLUDED from classifier
splits later (leakage guard, D6).

Export: templates_v2.jsonl -> outputs/study_b/r3/templates/<source>/<doc_id>.template.json
        ({"title": doc_id, "template": {...}} - the shape compare_sources loads).
--raw additionally exports outputs/study_b/r3/templates_raw/... with the full
post text in place of the template (template-vs-direct ablation).

  .venv/bin/python -m study_b.r3_pipeline_input [--n-docs 100] [--raw]
"""
import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

OUT = Path("outputs/study_b/r3")
SEED = 202609


def select_pool(n: int) -> list[str]:
    import pandas as pd
    h = pd.read_parquet("outputs/study_b/corpus/story_human_frozen.parquet")
    by_vert = defaultdict(list)
    for r in h.itertuples():
        by_vert[r.vertical].append(r.doc_id)
    rng = random.Random(SEED)
    total = len(h)
    picked = []
    # proportional allocation, at least 1 per non-empty stratum
    for v in sorted(by_vert):
        ids = sorted(by_vert[v])
        k = max(1, round(n * len(ids) / total))
        picked += rng.sample(ids, min(k, len(ids)))
    rng.shuffle(picked)
    return picked[:n]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-docs", type=int, default=100)
    ap.add_argument("--raw", action="store_true",
                    help="also export raw-text variant for the ablation")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    pool_file = OUT / "discovery_pool.json"
    if pool_file.exists():
        pool = set(json.loads(pool_file.read_text())["doc_ids"])
        print(f"pool exists: {len(pool)} docs (delete to redraw)", file=sys.stderr)
    else:
        pool = set(select_pool(args.n_docs))
        pool_file.write_text(json.dumps(
            {"seed": SEED, "n": len(pool), "doc_ids": sorted(pool)}, indent=2))
        print(f"pool drawn: {len(pool)} docs (seed {SEED})", file=sys.stderr)

    n_tpl = 0
    for line in open("outputs/study_b/templates/templates_v2.jsonl"):
        r = json.loads(line)
        if r["doc_id"] not in pool or "template" not in r:
            continue
        d = OUT / "templates" / r["source"]
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{r['doc_id']}.template.json").write_text(json.dumps(
            {"title": r["doc_id"], "template": r["template"]},
            ensure_ascii=False))
        n_tpl += 1
    print(f"exported {n_tpl} templates for {len(pool)} pool docs", file=sys.stderr)

    if args.raw:
        import pandas as pd
        h = pd.read_parquet("outputs/study_b/corpus/story_human_frozen.parquet")
        n_raw = 0
        for r in h.itertuples():
            if r.doc_id in pool:
                d = OUT / "templates_raw" / "human"
                d.mkdir(parents=True, exist_ok=True)
                (d / f"{r.doc_id}.template.json").write_text(json.dumps(
                    {"title": r.doc_id,
                     "template": {"full_text": r.story_human}}, ensure_ascii=False))
                n_raw += 1
        for f in sorted(Path("outputs/study_b/mirrors").glob("story_*.jsonl")):
            for line in open(f):
                r = json.loads(line)
                if r["doc_id"] in pool:
                    d = OUT / "templates_raw" / r["source"]
                    d.mkdir(parents=True, exist_ok=True)
                    (d / f"{r['doc_id']}.template.json").write_text(json.dumps(
                        {"title": r["doc_id"],
                         "template": {"full_text": r["text"]}}, ensure_ascii=False))
                    n_raw += 1
        print(f"exported {n_raw} raw-text docs (ablation)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
