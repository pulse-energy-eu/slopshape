#!/usr/bin/env python
"""Union taxonomy across discovery runs - shape-corrected for our runs.

The vendored build_taxonomy expects run files shaped {dim: {"aspects": ...}};
our discover runs save the aspect prompt's FULL response per dimension:
{dim: {"taxonomy_metadata": ..., "feature_taxonomy": {dim: {"aspects": ...}},
"feature_index": ...}} - one level deeper, so the vendored merge silently
yields an empty union (caught 2026-08-14, zero-candidate screen). This driver
flattens both shapes, then reuses the vendored union/variant-selection logic
(seed 42) and metadata computation verbatim.

  .venv/bin/python -m study_b.r3_union --input-dir outputs/study_b/r3/discovery \
      --output outputs/study_b/r3/taxonomy_union.json
"""
import argparse
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "vendor/storyscope"))

bt = importlib.import_module("storyscope.4_feature_discovery.build_taxonomy")


def flatten_run(tax: dict) -> dict:
    """Normalize one run's taxonomy to {dim: {"aspects": {...}}}."""
    flat = {}
    for dim_key, dim_data in tax.items():
        if not isinstance(dim_data, dict):
            continue
        if "aspects" in dim_data:  # vendored shape
            flat[dim_key] = dim_data
            continue
        inner = dim_data.get("feature_taxonomy", {})
        # the aspect prompts key the inner taxonomy by the dimension key,
        # but tolerate any single-key inner dict
        for k, v in inner.items():
            if isinstance(v, dict) and "aspects" in v:
                flat[dim_key] = {"aspects": v["aspects"]}
                break
    return flat


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    runs = bt.load_run_taxonomies(args.input_dir)
    flat_runs = [flatten_run(t) for t in runs]
    per_run = [sum(len(a.get("features", []))
                   for d in t.values() for a in d.get("aspects", {}).values())
               for t in flat_runs]
    print(f"features per run: {per_run}", file=sys.stderr)
    assert all(n > 0 for n in per_run), "a run flattened to zero features"

    features_by_id = bt.collect_all_features(flat_runs)
    union = bt.build_union_taxonomy(features_by_id, seed=args.seed)
    meta = bt.compute_metadata(union)
    out = {"taxonomy_metadata": meta, "feature_taxonomy": union}
    Path(args.output).write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"union: {meta['total_features']} unique features "
          f"({len(features_by_id)} ids) -> {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
