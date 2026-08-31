#!/usr/bin/env python
"""R6a: encode the answer matrix, cut domain-disjoint splits, fill the freeze
manifest.

Encoding (D9, per the paper's stated scheme with their released-code bugs
fixed): binary/categorical -> one-hot over the allowed values; multi_select ->
multi-hot; ordinal/scale -> integer position in the allowed-value list
(missing/off-menu -> NaN, XGBoost-native missing handling).

Instrument: the 214 surviving features (266 minus the 52 outcome-blind
exclusions). Variant sets derived from the R4 style audit:
  narrative_strict (HEADLINE) = surviving minus style-excluded
  style_only                  = surviving  intersect style-excluded
  all_features                = all 214

Splits: domain-disjoint at paper ratios (72.6/13.8/13.6), discovery-pool docs
excluded from everything, seed committed.

  .venv/bin/python -m study_b.r6_build
"""
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from study_b.r5_apply import load_features  # noqa: E402
from study_b.r5_qa import canon  # noqa: E402

OUT = Path("outputs/study_b/r6")
SPLIT_SEED = 202616
RATIOS = (0.726, 0.138, 0.136)  # paper 7383/1405/1384


def surviving_features():
    by_dim = load_features()
    excl = json.load(open("outputs/study_b/r5/feature_exclusions.json"))["exclusions"]
    style_excl = set(json.load(open("outputs/study_b/r4/excluded_features.json")))
    feats = []
    for dim, fs in by_dim.items():
        for f in fs:
            if f["id"] in excl:
                continue
            feats.append({**f, "dim": dim, "is_style": f["id"] in style_excl})
    return feats


def main() -> int:
    import numpy as np
    import pandas as pd

    OUT.mkdir(parents=True, exist_ok=True)
    feats = surviving_features()
    print(f"instrument: {len(feats)} features "
          f"({sum(f['is_style'] for f in feats)} style)", file=sys.stderr)

    # ---- collect answers for surviving features
    want = {f["id"] for f in feats}
    answers = defaultdict(dict)  # (doc_id, source) -> {fid: canon}
    for l in open("outputs/study_b/r5/answers_full.jsonl"):
        r = json.loads(l)
        if "answers" in r:
            for fid, v in r["answers"].items():
                if fid in want:
                    answers[(r["doc_id"], r["source"])][fid] = canon(v)

    # ---- encode
    cols = {}
    for f in feats:
        vals = [canon(v) for v in f.get("values", [])]
        if f.get("type") == "multi_select":
            for v in vals:
                cols[f"{f['id']}__{v}"] = ("multi", f["id"], v)
        elif f.get("type") in ("ordinal", "scale"):
            cols[f"{f['id']}__ord"] = ("ord", f["id"], vals)
        else:
            for v in vals:
                cols[f"{f['id']}__{v}"] = ("onehot", f["id"], v)
    col_names = sorted(cols)
    print(f"encoded columns: {len(col_names)}", file=sys.stderr)

    h = pd.read_parquet("outputs/study_b/corpus/story_human_frozen.parquet")
    meta_by_doc = {r.doc_id: (r.domain, r.vertical, r.stratum) for r in h.itertuples()}
    pool = set(json.loads(Path("outputs/study_b/r3/discovery_pool.json").read_text())["doc_ids"])

    rows, metas = [], []
    for (doc_id, source), fa in sorted(answers.items()):
        if doc_id in pool:
            continue
        row = np.full(len(col_names), np.nan, dtype=np.float32)
        for j, cn in enumerate(col_names):
            kind, fid, spec = cols[cn]
            a = fa.get(fid)
            if a is None:
                continue
            if kind == "onehot":
                row[j] = 1.0 if a == spec else 0.0
            elif kind == "multi":
                parts = set(a.split("|")) if a else set()
                row[j] = 1.0 if spec in parts else 0.0
            else:  # ordinal
                row[j] = float(spec.index(a)) if a in spec else np.nan
        dom, vert, strat = meta_by_doc.get(doc_id, ("", "", ""))
        rows.append(row)
        metas.append({"doc_id": doc_id, "source": source,
                      "label_ai": 0 if source == "human" else 1,
                      "domain": dom, "vertical": vert, "stratum": strat})
    X = pd.DataFrame(np.vstack(rows), columns=col_names)
    M = pd.DataFrame(metas)
    df = pd.concat([M, X], axis=1)
    df.to_parquet(OUT / "features_encoded.parquet")
    print(f"matrix: {len(df)} texts x {len(col_names)} columns "
          f"({df.doc_id.nunique()} docs)", file=sys.stderr)

    # ---- domain-disjoint splits
    import random
    doc_domain = {m["doc_id"]: m["domain"] for m in metas}
    by_domain = defaultdict(set)
    for d, dom in doc_domain.items():
        by_domain[dom].add(d)
    domains = sorted(by_domain)
    random.Random(SPLIT_SEED).shuffle(domains)
    n_docs = len(doc_domain)
    splits, acc = {}, 0
    targets = [RATIOS[0] * n_docs, (RATIOS[0] + RATIOS[1]) * n_docs]
    for dom in domains:
        part = "train" if acc < targets[0] else ("val" if acc < targets[1] else "test")
        splits[dom] = part
        acc += len(by_domain[dom])
    split_of_doc = {d: splits[dom] for d, dom in doc_domain.items()}
    counts = defaultdict(int)
    for d, s in split_of_doc.items():
        counts[s] += 1
    json.dump({"seed": SPLIT_SEED, "ratios": RATIOS, "domain_split": splits,
               "doc_split": split_of_doc, "doc_counts": dict(counts)},
              open(OUT / "splits.json", "w"), indent=2)
    print(f"splits (docs): {dict(counts)}", file=sys.stderr)

    # ---- feature variant sets
    variants = {
        "narrative_strict": sorted(f["id"] for f in feats if not f["is_style"]),
        "style_only": sorted(f["id"] for f in feats if f["is_style"]),
        "all_features": sorted(f["id"] for f in feats),
    }
    json.dump(variants, open(OUT / "variant_sets.json", "w"), indent=2)
    print({k: len(v) for k, v in variants.items()}, file=sys.stderr)

    # ---- freeze manifest
    def sha(p):
        return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]
    grid = {"n_estimators": [210, 420, 840], "max_depth": [4, 8, 12],
            "learning_rate": [0.05, 0.1, 0.2],
            "scale_pos_weight": [1.0, 2.5, 5.0, 7.5]}
    manifest = f"""# FREEZE_MANIFEST_RUN2 (filled {__import__('datetime').date.today()})

Committed before any full-corpus classification number is computed.

| Item | Value |
|---|---|
| Instrument | 214 features (266 deduped minus 52 outcome-blind exclusions) |
| Taxonomy hash | {sha('outputs/study_b/r3/dedup/condensed_taxonomy_0.85.json')} |
| Exclusions hash | {sha('outputs/study_b/r5/feature_exclusions.json')} |
| Style boundary | R4 strict rule (writing_style dim OR majority-high); hash {sha('outputs/study_b/r4/excluded_features.json')} |
| Encoder | one-hot nominal/binary, multi-hot multi_select, ordinal position, NaN missing (D9) |
| Encoded matrix hash | {sha(OUT / 'features_encoded.parquet')} |
| Splits | domain-disjoint {RATIOS}, seed {SPLIT_SEED}, discovery pool excluded; hash {sha(OUT / 'splits.json')} |
| Doc counts | {dict(counts)} |
| Task | HEADLINE: binary human-vs-AI, narrative_strict variant, macro-F1 + AUPRC; secondary 6-way (macro-F1 + accuracy) |
| Grid (val-selected) | {json.dumps(grid)} |
| Variants | narrative_strict {len(variants['narrative_strict'])}, style_only {len(variants['style_only'])}, all_features {len(variants['all_features'])}, core-only + core+FP per SHAP-bootstrap B=50 (paper section D thresholds) |
| CIs | 10k bootstrap, prompt-level AND domain-cluster (cluster primary), seed {SPLIT_SEED} |
| Analysis list | SPEC 3.7 items 1-18 |
"""
    Path(OUT / "FREEZE_MANIFEST_RUN2.md").write_text(manifest)
    # compare against the frozen artifacts/FREEZE_MANIFEST_RUN2.md
    print("manifest written", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
