#!/usr/bin/env python
"""R6b: grid search, training, variants, SHAP, bootstrap CIs.

All results are written plainly to outputs/study_b/r6/results/ - train, val,
and test alike (PI directive 2026-08-16: no access gating).

Per variant: 108-config grid on val (macro-F1), final model refit on train,
metrics on train/val/test with binary macro-F1 + AUPRC; the 6-way task runs
on the narrative_strict variant with the val-chosen config. SHAP on the
headline model; core/fingerprint selection via B=50 prompt-resampled
bootstrap SHAP (paper section D thresholds) -> core_only and core_fp variants.

  .venv/bin/python -m study_b.r6_train [--variants narrative_strict,...]
"""
import argparse
import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

OUT = Path("outputs/study_b/r6")
RES = OUT / "results"
SEED = 202616
GRID = {"n_estimators": [210, 420, 840], "max_depth": [4, 8, 12],
        "learning_rate": [0.05, 0.1, 0.2],
        "scale_pos_weight": [1.0, 2.5, 5.0, 7.5]}


def load():
    import pandas as pd
    df = pd.read_parquet(OUT / "features_encoded.parquet")
    splits = json.load(open(OUT / "splits.json"))["doc_split"]
    df["split"] = df.doc_id.map(splits)
    variants = json.load(open(OUT / "variant_sets.json"))
    return df, variants


def cols_for(df, fids):
    pref = tuple(f"{fid}__" for fid in fids)
    return [c for c in df.columns if c.startswith(pref)]


def metrics_binary(y, p, proba):
    from sklearn.metrics import f1_score, average_precision_score, accuracy_score
    return {"macro_f1": round(float(f1_score(y, p, average="macro")), 4),
            "auprc": round(float(average_precision_score(y, proba)), 4),
            "accuracy": round(float(accuracy_score(y, p)), 4)}


def fit(Xtr, ytr, cfg):
    import xgboost as xgb
    m = xgb.XGBClassifier(random_state=SEED, n_jobs=-1, tree_method="hist",
                          eval_metric="logloss", **cfg)
    m.fit(Xtr, ytr)
    return m


def grid_search(df, cols, log):
    from sklearn.metrics import f1_score
    tr = df[df.split == "train"]
    va = df[df.split == "val"]
    best, best_cfg = -1, None
    for i, vals in enumerate(itertools.product(*GRID.values()), 1):
        cfg = dict(zip(GRID.keys(), vals))
        m = fit(tr[cols], tr.label_ai, cfg)
        f1 = f1_score(va.label_ai, m.predict(va[cols]), average="macro")
        if f1 > best:
            best, best_cfg = f1, cfg
        if i % 20 == 0:
            print(f"  grid {i}/108 best_val_f1={best:.4f}", file=log, flush=True)
    return best_cfg, round(float(best), 4)


def evaluate(df, cols, m, name):
    out = {}
    for split in ("train", "val", "test"):
        part = df[df.split == split]
        proba = m.predict_proba(part[cols])[:, 1]
        out[split] = metrics_binary(part.label_ai, (proba >= 0.5).astype(int), proba)
    return out


def bootstrap_ci(df, cols, m, n=10000):
    """Test-set CIs: prompt-level and domain-cluster resampling."""
    import numpy as np
    from sklearn.metrics import f1_score
    te = df[df.split == "test"].reset_index(drop=True)
    proba = m.predict_proba(te[cols])[:, 1]
    pred = (proba >= 0.5).astype(int)
    y = te.label_ai.to_numpy()
    rng = np.random.default_rng(SEED)
    docs = te.doc_id.to_numpy()
    doms = te.domain.to_numpy()
    uniq_docs = np.unique(docs)
    uniq_doms = np.unique(doms)
    doc_idx = {d: np.flatnonzero(docs == d) for d in uniq_docs}
    dom_idx = {d: np.flatnonzero(doms == d) for d in uniq_doms}
    out = {}
    for label, units, index in (("prompt", uniq_docs, doc_idx),
                                ("domain_cluster", uniq_doms, dom_idx)):
        stats = []
        for _ in range(n):
            pick = rng.choice(units, size=len(units), replace=True)
            idx = np.concatenate([index[u] for u in pick])
            stats.append(f1_score(y[idx], pred[idx], average="macro"))
        lo, hi = np.percentile(stats, [2.5, 97.5])
        out[label] = {"ci95": [round(float(lo), 4), round(float(hi), 4)]}
    return out


def shap_core_selection(df, cols, cfg, fids, log):
    """B=50 prompt-resampled bootstrap SHAP -> core/fingerprint per paper D."""
    import numpy as np
    import shap
    tr = df[df.split.isin(["train", "val"])].reset_index(drop=True)
    rng = np.random.default_rng(SEED)
    docs = tr.doc_id.unique()
    col_to_fid = {c: c.split("__")[0] for c in cols}
    mean_shap_runs = []
    for b in range(50):
        pick = rng.choice(docs, size=len(docs), replace=True)
        sub = tr[tr.doc_id.isin(set(pick))]
        m = fit(sub[cols], sub.label_ai, cfg)
        ex = shap.TreeExplainer(m)
        sv = ex.shap_values(sub[cols].sample(min(800, len(sub)), random_state=b))
        mean_abs = np.abs(sv).mean(axis=0)
        per_fid = {}
        for c, v in zip(cols, mean_abs):
            per_fid[col_to_fid[c]] = per_fid.get(col_to_fid[c], 0.0) + float(v)
        mean_shap_runs.append(per_fid)
        if (b + 1) % 10 == 0:
            print(f"  shap bootstrap {b+1}/50", file=log, flush=True)
    import pandas as pd
    S = pd.DataFrame(mean_shap_runs).fillna(0.0)
    meanv = S.mean()
    q75 = meanv.quantile(0.75)
    important_rate = (S >= S.quantile(0.75, axis=1).values[:, None]).mean()
    stability = important_rate  # share of runs where feature is top-quartile
    core = sorted(f for f in S.columns
                  if stability[f] >= 0.55 and meanv[f] >= q75)
    ranked = meanv.sort_values(ascending=False)
    fingerprint = sorted(set(ranked.head(int(len(ranked) * 0.4)).index) - set(core))
    return {"mean_shap": {k: round(float(v), 6) for k, v in meanv.items()},
            "core": core, "fingerprint": fingerprint}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", default="narrative_strict,style_only,all_features")
    args = ap.parse_args()
    RES.mkdir(parents=True, exist_ok=True)
    df, variants = load()
    log = sys.stderr

    results = {}
    chosen = {}
    for name in args.variants.split(","):
        fids = variants[name]
        cols = cols_for(df, fids)
        print(f"=== variant {name}: {len(fids)} features / {len(cols)} cols ===",
              file=log, flush=True)
        cfg, val_f1 = grid_search(df, cols, log)
        m = fit(df[df.split == "train"][cols], df[df.split == "train"].label_ai, cfg)
        res = {"config": cfg, "grid_best_val_f1": val_f1,
               "metrics": evaluate(df, cols, m, name)}
        if name == "narrative_strict":
            res["test_ci"] = bootstrap_ci(df, cols, m)
        results[name] = res
        chosen[name] = cfg
        json.dump(results, open(RES / "variant_results.json", "w"), indent=2)
        print(f"variant {name} done: {json.dumps(res['metrics'])}", file=log, flush=True)

    # 6-way on narrative_strict with its chosen config
    from sklearn.metrics import f1_score, accuracy_score
    from sklearn.preprocessing import LabelEncoder
    cols = cols_for(df, variants["narrative_strict"])
    le = LabelEncoder()
    y6 = le.fit_transform(df.source)
    import xgboost as xgb
    cfg6 = {k: v for k, v in chosen["narrative_strict"].items() if k != "scale_pos_weight"}
    m6 = xgb.XGBClassifier(random_state=SEED, n_jobs=-1, tree_method="hist",
                           eval_metric="mlogloss", **cfg6)
    trm = df.split == "train"
    m6.fit(df[trm][cols], y6[trm])
    six = {}
    for split in ("train", "val", "test"):
        mask = df.split == split
        pred = m6.predict(df[mask][cols])
        six[split] = {"macro_f1": round(float(f1_score(y6[mask], pred, average="macro")), 4),
                      "accuracy": round(float(accuracy_score(y6[mask], pred)), 4)}
    json.dump({"classes": list(le.classes_), "metrics": six},
              open(RES / "sixway_results.json", "w"), indent=2)
    print(f"6-way done: {json.dumps(six)}", file=log, flush=True)

    # SHAP + core/fingerprint -> two more variants
    sel = shap_core_selection(df, cols, chosen["narrative_strict"],
                              variants["narrative_strict"], log)
    json.dump(sel, open(RES / "shap_core_selection.json", "w"), indent=2)
    for name, fids in (("core_only", sel["core"]),
                       ("core_fp", sorted(set(sel["core"]) | set(sel["fingerprint"])))):
        if not fids:
            continue
        vcols = cols_for(df, fids)
        cfg, val_f1 = grid_search(df, vcols, log)
        m = fit(df[df.split == "train"][vcols], df[df.split == "train"].label_ai, cfg)
        results[name] = {"n_features": len(fids), "config": cfg,
                         "grid_best_val_f1": val_f1,
                         "metrics": evaluate(df, vcols, m, name)}
        json.dump(results, open(RES / "variant_results.json", "w"), indent=2)
        print(f"variant {name} done", file=log, flush=True)

    print("R6 TRAIN DONE", file=log, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
