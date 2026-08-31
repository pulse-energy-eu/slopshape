#!/usr/bin/env python
"""Protocol-parity fix batch (2026-08-19 audit; P1-P6).

P1 final models retrained on TRAIN+VAL (original L1135-39) - all variants +
   CIs recomputed; grid selection stays val-based (unchanged).
P2 core/fingerprint per the original section D: permutation-null p<=0.10,
   stability >= 0.55, top25 >= 0.60, |gap| >= 0.20, AI-spread <= 0.35;
   fingerprints from 6-WAY per-class SHAP concentration.
P3 grid gains reg_lambda (their published constant 2.0); 6-way gets its own
   grid centered on their 500/7/1.0.
P4 pre-specified delta tests: bootstrap CI on the narrative-minus-style gap
   + H1' TOST vs the original's 93.2 (margin 2.0, per prereg Amendment 1).
P5 near-verbatim memorization rule + n-gram-filtered rerun.
P6 rarity AUC, per-class 6-way F1, length tertile bands.

  .venv/bin/python -m study_b.r6_parity_fixes
"""
import itertools
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from study_b.r6_train import load, cols_for, metrics_binary  # noqa: E402

OUT = Path("outputs/study_b/r6/results")
SEED = 202616
GRID_BIN = {"n_estimators": [210, 420, 840], "max_depth": [4, 8, 12],
            "reg_lambda": [1.0, 2.0, 4.0],
            "scale_pos_weight": [1.0, 2.5, 5.0, 7.5]}
GRID_SIX = {"n_estimators": [250, 500, 1000], "max_depth": [5, 7, 9],
            "reg_lambda": [0.5, 1.0, 2.0]}


def fit(X, y, cfg, num_class=None):
    import xgboost as xgb
    kw = dict(random_state=SEED, n_jobs=-1, tree_method="hist", **cfg)
    if num_class:
        return xgb.XGBClassifier(eval_metric="mlogloss", **kw).fit(X, y)
    return xgb.XGBClassifier(eval_metric="logloss", **kw).fit(X, y)


def main() -> int:
    import pandas as pd
    from sklearn.metrics import f1_score, average_precision_score
    df, variants = load()
    R = {}

    # ---------------- P1+P3: re-grid (with lambda) + train+val finals -------
    results = {}
    chosen = {}
    for name in ("narrative_strict", "style_only", "all_features"):
        cols = cols_for(df, variants[name])
        tr = df[df.split == "train"]; va = df[df.split == "val"]
        trval = df[df.split.isin(["train", "val"])]; te = df[df.split == "test"]
        best, best_cfg = -1, None
        for vals in itertools.product(*GRID_BIN.values()):
            cfg = dict(zip(GRID_BIN.keys(), vals))
            m = fit(tr[cols], tr.label_ai, cfg)
            f1 = f1_score(va.label_ai, m.predict(va[cols]), average="macro")
            if f1 > best:
                best, best_cfg = f1, cfg
        m = fit(trval[cols], trval.label_ai, best_cfg)  # P1: final on train+val
        proba = m.predict_proba(te[cols])[:, 1]
        pred = (proba >= 0.5).astype(int)
        results[name] = {"config": best_cfg, "grid_best_val_f1": round(float(best), 4),
                         "final_fit": "train+val (original protocol)",
                         "test": metrics_binary(te.label_ai, pred, proba)}
        chosen[name] = best_cfg
        print(f"P1 {name}: {json.dumps(results[name]['test'])}", flush=True)

    # cluster+prompt bootstrap CI for headline (recomputed under P1)
    cols = cols_for(df, variants["narrative_strict"])
    trval = df[df.split.isin(["train", "val"])]; te = df[df.split == "test"].reset_index(drop=True)
    m_head = fit(trval[cols], trval.label_ai, chosen["narrative_strict"])
    proba = m_head.predict_proba(te[cols])[:, 1]
    pred = (proba >= 0.5).astype(int)
    y = te.label_ai.to_numpy()
    rng = np.random.default_rng(SEED)
    for label, unit_col in (("prompt", "doc_id"), ("domain_cluster", "domain")):
        units = te[unit_col].to_numpy()
        uniq = np.unique(units)
        idx = {u: np.flatnonzero(units == u) for u in uniq}
        stats = []
        for _ in range(10000):
            pick = rng.choice(uniq, size=len(uniq), replace=True)
            ii = np.concatenate([idx[u] for u in pick])
            stats.append(f1_score(y[ii], pred[ii], average="macro"))
        lo, hi = np.percentile(stats, [2.5, 97.5])
        results["narrative_strict"].setdefault("test_ci", {})[label] = {
            "ci95": [round(float(lo), 4), round(float(hi), 4)]}
    print("P1 headline CI:", json.dumps(results["narrative_strict"]["test_ci"]), flush=True)

    # ---------------- P4: delta tests + TOST --------------------------------
    cols_s = cols_for(df, variants["style_only"])
    m_style = fit(trval[cols_s], trval.label_ai, chosen["style_only"])
    pred_s = m_style.predict(te[cols_s])
    doc_units = te.doc_id.to_numpy(); uniq = np.unique(doc_units)
    idx = {u: np.flatnonzero(doc_units == u) for u in uniq}
    deltas = []
    for _ in range(10000):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        ii = np.concatenate([idx[u] for u in pick])
        deltas.append(f1_score(y[ii], pred[ii], average="macro")
                      - f1_score(y[ii], pred_s[ii], average="macro"))
    dlo, dhi = np.percentile(deltas, [2.5, 97.5])
    R["h1_direction"] = {
        "narrative_minus_style_delta": round(float(np.mean(deltas)), 4),
        "ci95": [round(float(dlo), 4), round(float(dhi), 4)],
        "confirmed_direction": bool(dlo > 0),
        "original_delta": "93.2 - 85.8 = 7.4 (CI 2.09-3.54 on their scale)"}
    # TOST vs original 93.2 (margin +-2.0 pts on macro-F1*100), prompt bootstrap
    head_stats = []
    for _ in range(10000):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        ii = np.concatenate([idx[u] for u in pick])
        head_stats.append(f1_score(y[ii], pred[ii], average="macro") * 100)
    hlo, hhi = np.percentile(head_stats, [2.5, 97.5])
    inside = (hlo >= 93.2 - 2.0) and (hhi <= 93.2 + 2.0)
    R["h1_tost_vs_original"] = {
        "our_headline_pct": round(float(np.mean(head_stats)), 2),
        "ci95": [round(float(hlo), 2), round(float(hhi), 2)],
        "equivalence_band": [91.2, 95.2],
        "equivalent": bool(inside),
        "reading": ("equivalent" if inside else
                    ("stronger (CI above band)" if hlo > 95.2 else "not equivalent"))}
    print("P4:", json.dumps({k: R[k] for k in ("h1_direction", "h1_tost_vs_original")}), flush=True)

    # ---------------- P2: core/fingerprint per section D --------------------
    import shap
    import xgboost as xgb
    col_to_fid = {c: c.split("__")[0] for c in cols}
    docs = trval.doc_id.unique()
    boot_shap = []
    for b in range(50):
        pick = np.random.default_rng(b).choice(docs, size=len(docs), replace=True)
        sub = trval[trval.doc_id.isin(set(pick))]
        mb = fit(sub[cols], sub.label_ai, chosen["narrative_strict"])
        sv = shap.TreeExplainer(mb).shap_values(sub[cols].sample(600, random_state=b))
        ma = np.abs(sv).mean(axis=0)
        per = {}
        for c, v in zip(cols, ma):
            per[col_to_fid[c]] = per.get(col_to_fid[c], 0.0) + float(v)
        boot_shap.append(per)
        if (b + 1) % 10 == 0:
            print(f"P2 shap boot {b+1}/50", flush=True)
    S = pd.DataFrame(boot_shap).fillna(0.0)
    meanv = S.mean()
    q75 = meanv.quantile(0.75)
    important = meanv[meanv >= q75].index
    stab = (S.ge(S.quantile(0.75, axis=1), axis=0)).mean()  # share of runs top-quartile
    top25 = (S.rank(axis=1, ascending=False) <= 25).mean()
    # permutation null: label-shuffled SHAP (5 permutations, 95th pct null)
    null_means = []
    for pnum in range(5):
        sub = trval.sample(frac=1.0, random_state=100 + pnum)
        ysh = sub.label_ai.sample(frac=1.0, random_state=200 + pnum).to_numpy()
        mp = fit(sub[cols], ysh, chosen["narrative_strict"])
        sv = shap.TreeExplainer(mp).shap_values(sub[cols].sample(600, random_state=pnum))
        ma = np.abs(sv).mean(axis=0)
        per = {}
        for c, v in zip(cols, ma):
            per[col_to_fid[c]] = per.get(col_to_fid[c], 0.0) + float(v)
        null_means.append(per)
        print(f"P2 null perm {pnum+1}/5", flush=True)
    NS = pd.DataFrame(null_means).fillna(0.0)
    null95 = NS.quantile(0.95)
    # per-feature human-AI gap and AI spread on NORMALIZED per-feature answer means
    fidcols = {}
    for c in cols:
        fidcols.setdefault(col_to_fid[c], []).append(c)
    gaps, spreads = {}, {}
    for fid, cc in fidcols.items():
        vals = df[cc].mean(axis=1)  # crude per-feature scalar (mean of encoded cols)
        hmean = vals[df.source == "human"].mean()
        ai_means = [vals[df.source == s_].mean() for s_ in
                    ("gpt", "claude", "gemini", "deepseek", "kimi")]
        gaps[fid] = abs(hmean - np.mean(ai_means))
        spreads[fid] = max(ai_means) - min(ai_means)
    gap_s = pd.Series(gaps); spread_s = pd.Series(spreads)
    # normalize gap/spread scales to [0,1] within feature set for thresholding
    gap_n = gap_s / max(1e-9, gap_s.max())
    spread_n = spread_s / max(1e-9, spread_s.max())
    core = sorted(f for f in important
                  if stab.get(f, 0) >= 0.55 and top25.get(f, 0) >= 0.60
                  and meanv[f] > null95.get(f, 0)
                  and gap_n.get(f, 0) >= 0.20 and spread_n.get(f, 1) <= 0.35)
    # fingerprints: 6-way per-class SHAP concentration
    from sklearn.preprocessing import LabelEncoder
    le = LabelEncoder(); y6 = le.fit_transform(df.source)
    trv6 = df.split.isin(["train", "val"])
    # 6-way grid (P3)
    best6, cfg6b = -1, None
    trm = df.split == "train"; vam = df.split == "val"
    for vals in itertools.product(*GRID_SIX.values()):
        cfg6 = dict(zip(GRID_SIX.keys(), vals))
        m6 = fit(df[trm][cols], y6[trm], cfg6, num_class=6)
        f16 = f1_score(y6[vam], m6.predict(df[vam][cols]), average="macro")
        if f16 > best6:
            best6, cfg6b = f16, cfg6
    m6 = fit(df[trv6][cols], y6[trv6], cfg6b, num_class=6)
    sv6 = shap.TreeExplainer(m6).shap_values(df[trv6][cols].sample(800, random_state=SEED))
    sv6 = np.array(sv6)  # (classes, n, cols) or (n, cols, classes)
    if sv6.ndim == 3 and sv6.shape[0] != 6:
        sv6 = np.moveaxis(sv6, -1, 0)
    per_class = np.abs(sv6).mean(axis=1)  # (6, cols)
    fp = {}
    for ci_, cls in enumerate(le.classes_):
        agg = {}
        for c, v in zip(cols, per_class[ci_]):
            agg[col_to_fid[c]] = agg.get(col_to_fid[c], 0.0) + float(v)
        fp[cls] = agg
    FP = pd.DataFrame(fp).fillna(0.0)
    conc = FP.div(FP.sum(axis=1) + 1e-12, axis=0)  # share per class
    fingerprints = {}
    for fid in FP.index:
        if fid in core:
            continue
        shares = conc.loc[fid]
        if shares.max() >= 0.5 and FP.loc[fid].max() > null95.get(fid, 0):
            fingerprints.setdefault(shares.idxmax(), []).append(fid)
    te6 = df.split == "test"
    pred6 = m6.predict(df[te6][cols])
    perclass_f1 = f1_score(y6[te6], pred6, average=None)
    R["p2_core_fingerprint"] = {
        "core_n": len(core), "core": core,
        "fingerprint_counts": {k: len(v) for k, v in sorted(fingerprints.items())},
        "fingerprints": fingerprints,
        "sixway_config": cfg6b, "sixway_val_f1": round(float(best6), 4),
        "sixway_test_perclass_f1": {cls: round(float(f), 3)
                                    for cls, f in zip(le.classes_, perclass_f1)},
        "sixway_test_macro_f1": round(float(f1_score(y6[te6], pred6, average='macro')), 4)}
    print("P2:", json.dumps({k: R["p2_core_fingerprint"][k] for k in
                             ("core_n", "fingerprint_counts", "sixway_test_macro_f1")}), flush=True)
    # core-only / core+fp variants under P1 protocol
    for nm, fids in (("core_only", core),
                     ("core_fp", sorted(set(core) | {f for v in fingerprints.values() for f in v}))):
        if not fids:
            continue
        vcols = cols_for(df, fids)
        mv = fit(trval[vcols], trval.label_ai, chosen["narrative_strict"])
        proba_v = mv.predict_proba(te[vcols])[:, 1]
        results[nm] = {"n_features": len(fids), "final_fit": "train+val",
                       "test": metrics_binary(te.label_ai, (proba_v >= .5).astype(int), proba_v)}
    json.dump(results, open(OUT / "variant_results_parity.json", "w"), indent=2)

    # ---------------- P5: near-verbatim + filtered rerun --------------------
    h = pd.read_parquet("outputs/study_b/corpus/story_human_frozen.parquet")
    hum_text = h.set_index("doc_id").story_human.to_dict()
    def grams8(text):
        t = text.lower().split()
        return [" ".join(t[i:i+8]) for i in range(len(t) - 7)]
    flagged = set()
    for s_ in ("gpt", "claude", "gemini", "deepseek", "kimi"):
        for l in open(f"outputs/study_b/mirrors/story_{s_}.jsonl"):
            r = json.loads(l)
            ht = hum_text.get(r["doc_id"])
            if not ht:
                continue
            g_m = grams8(r["text"]); g_h = set(grams8(ht))
            hits = [g in g_h for g in g_m]
            cov = sum(hits) / max(1, len(hits))
            distinct = len({g for g, hit in zip(g_m, hits) if hit})
            if cov >= 0.05 and distinct >= 4:
                flagged.add((s_, r["doc_id"]))
    keep = ~te.apply(lambda r: (r.source, r.doc_id) in flagged, axis=1)
    R["p5_near_verbatim"] = {
        "flagged_pairs": len(flagged),
        "rate": round(len(flagged) / 11250, 5),
        "test_f1_filtered": round(float(f1_score(
            y[keep.to_numpy()], pred[keep.to_numpy()], average="macro")), 4),
        "test_rows_dropped": int((~keep).sum())}
    print("P5:", json.dumps(R["p5_near_verbatim"]), flush=True)

    # ---------------- P6: rarity AUC, length tertiles -----------------------
    from sklearn.metrics import roc_auc_score
    rar = pd.read_parquet(OUT / "rarity" / "rarity.parquet")
    R["p6_rarity_auc"] = round(float(roc_auc_score(
        (rar.source == "human").astype(int), rar.rarity_trainval)), 3)
    wc = {}
    for r_ in h.itertuples():
        wc[("human", r_.doc_id)] = r_.words
    for s_ in ("gpt", "claude", "gemini", "deepseek", "kimi"):
        for l in open(f"outputs/study_b/mirrors/story_{s_}.jsonl"):
            r = json.loads(l)
            wc[(s_, r["doc_id"])] = len(r["text"].split())
    te_w = te.apply(lambda r: wc.get((r.source, r.doc_id), np.nan), axis=1)
    terts = pd.qcut(te_w, 3, labels=["short", "mid", "long"])
    R["p6_length_tertiles_f1"] = {
        str(t): round(float(f1_score(y[(terts == t).to_numpy()],
                                     pred[(terts == t).to_numpy()],
                                     average="macro")), 4)
        for t in ("short", "mid", "long")}
    print("P6:", json.dumps({k: R[k] for k in ("p6_rarity_auc", "p6_length_tertiles_f1")}), flush=True)

    json.dump(R, open(OUT / "parity_fixes.json", "w"), indent=2)
    print("PARITY FIXES DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
