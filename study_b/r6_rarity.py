#!/usr/bin/env python
"""R6 rarity - v1's verified compute_rarity applied to the R6 encoded matrix.

v1's rarity.py loads the v1 pipeline's RAW-answer parquet via the vendored
encoder; R6 already ships an encoded matrix + committed splits, so this
adapter feeds compute_rarity directly (D7: re-implemented from text, verified
against their data in v1).

Protocol per the paper: z-scored matrix (narrative_strict columns, the
headline instrument), mean distance to 25 nearest reference neighbors,
percentile vs reference = train+val; also --reference all for robustness.
Reported: human vs AI mean percentile, Cohen's d, rarest-decile shares,
per-prompt "human is rarest" share (their 0.71/0.49, d 0.83, 24.7%/7.1%, 57.8%).

  .venv/bin/python -m study_b.r6_rarity
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from study_b.rarity import compute_rarity  # noqa: E402

OUT = Path("outputs/study_b/r6/results/rarity")


def main() -> int:
    import pandas as pd
    df = pd.read_parquet("outputs/study_b/r6/features_encoded.parquet")
    splits = json.load(open("outputs/study_b/r6/splits.json"))["doc_split"]
    variants = json.load(open("outputs/study_b/r6/variant_sets.json"))
    fids = variants["narrative_strict"]
    pref = tuple(f"{fid}__" for fid in fids)
    cols = [c for c in df.columns if c.startswith(pref)]
    X = df[cols].to_numpy(dtype=np.float32)
    X = np.nan_to_num(X, nan=0.0)
    mu, sd = X.mean(axis=0), X.std(axis=0)
    sd[sd == 0] = 1.0
    X = (X - mu) / sd

    df["split"] = df.doc_id.map(splits)
    OUT.mkdir(parents=True, exist_ok=True)
    report = {}
    for refname in ("trainval", "all"):
        ref = (df.split.isin(["train", "val"]) if refname == "trainval"
               else pd.Series(True, index=df.index)).to_numpy()
        pct = compute_rarity(X, ref)
        df[f"rarity_{refname}"] = pct
        hum = pct[df.label_ai == 0]
        ai = pct[df.label_ai == 1]
        pooled = np.sqrt((hum.std() ** 2 + ai.std() ** 2) / 2)
        d = (hum.mean() - ai.mean()) / max(1e-9, pooled)
        # per-prompt: is the human version the rarest of its 6 texts?
        byq = df.assign(p=pct).groupby("doc_id").apply(
            lambda g: g.loc[g.p.idxmax(), "source"] == "human",
            include_groups=False)
        report[refname] = {
            "human_mean": round(float(hum.mean()), 4),
            "ai_mean": round(float(ai.mean()), 4),
            "cohens_d": round(float(d), 4),
            "rarest_decile_human_share": round(float((hum >= 0.9).mean()), 4),
            "rarest_decile_ai_share": round(float((ai >= 0.9).mean()), 4),
            "human_rarest_of_prompt": round(float(byq.mean()), 4),
            "paper": {"human_mean": 0.71, "ai_mean": 0.49, "d": 0.83,
                      "decile": [0.247, 0.071], "human_rarest": 0.578},
        }
        print(f"{refname}: {json.dumps(report[refname])}")
    df[["doc_id", "source", "split", "rarity_trainval", "rarity_all"]].to_parquet(
        OUT / "rarity.parquet")
    json.dump(report, open(OUT / "rarity_report.json", "w"), indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
