#!/usr/bin/env python
"""Section-D core selection at VALUE granularity (the faithful unit).

The original selects core VALUES (30 features = 33 values): per encoded
value j, bootstrap SHAP (B=50, prompt-resampled) with mean|SHAP| top-quartile,
stability >= 0.55, top25 >= 0.60, permutation-null p <= 0.10 (95th pct null),
|human-AI value-mean gap| >= 0.20 (raw proportions), cross-model AI spread
<= 0.35 (raw). Fingerprints stay per the 6-way concentration pass (parity
batch). Final core-only/core+fp variants retrained train+val.

  .venv/bin/python -m study_b.r6_core_values
"""
import itertools
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from study_b.r6_train import load, cols_for, metrics_binary  # noqa: E402
from study_b.r6_parity_fixes import fit, GRID_BIN  # noqa: E402

OUT = Path("outputs/study_b/r6/results")
SEED = 202616


def main() -> int:
    import pandas as pd
    import shap
    from sklearn.metrics import f1_score

    df, variants = load()
    cols = cols_for(df, variants["narrative_strict"])
    parity = json.load(open(OUT / "variant_results_parity.json"))
    cfg = parity["narrative_strict"]["config"]
    trval = df[df.split.isin(["train", "val"])]
    te = df[df.split == "test"]

    # bootstrap SHAP at COLUMN granularity
    docs = trval.doc_id.unique()
    boots = []
    for b in range(50):
        pick = np.random.default_rng(b).choice(docs, size=len(docs), replace=True)
        sub = trval[trval.doc_id.isin(set(pick))]
        m = fit(sub[cols], sub.label_ai, cfg)
        sv = shap.TreeExplainer(m).shap_values(sub[cols].sample(600, random_state=b))
        boots.append(np.abs(sv).mean(axis=0))
        if (b + 1) % 10 == 0:
            print(f"boot {b+1}/50", flush=True)
    S = pd.DataFrame(boots, columns=cols)
    meanv = S.mean()
    q75 = meanv.quantile(0.75)
    stab = (S.ge(S.quantile(0.75, axis=1), axis=0)).mean()
    top25 = (S.rank(axis=1, ascending=False) <= 25).mean()

    # permutation null (5 label shuffles)
    nulls = []
    for pnum in range(5):
        sub = trval.sample(frac=1.0, random_state=100 + pnum)
        ysh = sub.label_ai.sample(frac=1.0, random_state=200 + pnum).to_numpy()
        m = fit(sub[cols], ysh, cfg)
        sv = shap.TreeExplainer(m).shap_values(sub[cols].sample(600, random_state=pnum))
        nulls.append(np.abs(sv).mean(axis=0))
        print(f"null {pnum+1}/5", flush=True)
    null95 = pd.DataFrame(nulls, columns=cols).quantile(0.95)

    # raw value-mean gaps and AI spread (proportions for one-hot/multi-hot;
    # ordinal columns rescaled to [0,1] by their max index)
    gaps, spreads, signs = {}, {}, {}
    for c in cols:
        v = df[c].astype(float)
        if c.endswith("__ord"):
            mx = v.max()
            if mx and mx > 0:
                v = v / mx
        hmean = v[df.source == "human"].mean()
        ai_means = [v[df.source == s_].mean() for s_ in
                    ("gpt", "claude", "gemini", "deepseek", "kimi")]
        gaps[c] = abs(hmean - float(np.mean(ai_means)))
        spreads[c] = float(max(ai_means) - min(ai_means))
        signs[c] = "human" if hmean > np.mean(ai_means) else "ai"

    core_values = sorted(
        c for c in cols
        if meanv[c] >= q75 and stab[c] >= 0.55 and top25[c] >= 0.60
        and meanv[c] > null95[c] and gaps[c] >= 0.20 and spreads[c] <= 0.35)
    core_features = sorted({c.split("__")[0] for c in core_values})
    print(f"core: {len(core_values)} values across {len(core_features)} features "
          f"(theirs: 33 values / 30 features)", flush=True)

    # variants under faithful protocol
    fp = json.load(open(OUT / "parity_fixes.json"))["p2_core_fingerprint"]["fingerprints"]
    fp_feats = sorted({f for v in fp.values() for f in v})
    res = {}
    for nm, fids in (("core_only", core_features),
                     ("core_fp", sorted(set(core_features) | set(fp_feats)))):
        if not fids:
            continue
        vcols = cols_for(df, fids)
        m = fit(trval[vcols], trval.label_ai, cfg)
        proba = m.predict_proba(te[vcols])[:, 1]
        res[nm] = {"n_features": len(fids),
                   "test": metrics_binary(te.label_ai, (proba >= .5).astype(int), proba)}
        print(nm, json.dumps(res[nm]), flush=True)

    # attribution share of the core features within the full structural
    # model: per-FEATURE bootstrap-mean |SHAP| from the SHAP bootstrap
    # output (mean_shap), summed over the core features vs all features
    # (the paper's "27.6% of the full model's feature attributions")
    ms = json.load(open(OUT / "shap_core_selection.json"))["mean_shap"]
    total_ms = sum(ms.values())
    core_ms = sum(ms[f] for f in core_features if f in ms)
    attribution = {
        "share": round(core_ms / total_ms, 4),
        "core_mean_abs_shap_sum": round(core_ms, 4),
        "total_mean_abs_shap_sum": round(total_ms, 4),
        "n_features_total": len(ms),
        "basis": ("per-feature bootstrap-mean |SHAP| of the structural "
                  "(narrative_strict) model (B=50, prompt-resampled; the "
                  "mean_shap block of the SHAP bootstrap output), summed "
                  "over the 10 core features vs all 187 structural "
                  "features; the paper's '27.6% of the full model's "
                  "feature attributions'")}
    print("core attribution share:", attribution["share"], flush=True)

    out = {"core_values": core_values, "core_features": core_features,
           "n_core_values": len(core_values), "n_core_features": len(core_features),
           "value_signs": {c: signs[c] for c in core_values},
           "value_gaps": {c: round(gaps[c], 3) for c in core_values},
           "variants": res,
           "core_attribution_share": attribution}
    json.dump(out, open(OUT / "core_values_selection.json", "w"), indent=2)
    print("CORE VALUES DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
