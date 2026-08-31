#!/usr/bin/env python
"""Pre-drafting review fixes (2026-08-20 external-review batch).

Computes, under the FAITHFUL protocol (final fits on train+val, frozen parity
config), the sensitivity batteries that had been run train-only (M2), plus the
two manifest-listed analyses that were missing (M6: error-overlap diagnostic,
learning curve), the faithful 6-way accuracy (m7), geometry extras (m17),
repeatability pairwise Cohen's kappa (m8), and the F7 length-boxplot figure
(m19). Length-matched (8.4) is NOT rerun: its matching-rule script did not
survive; it stays disclosed as train-only.

All outputs -> outputs/study_b/r6/results/review2_fixes.json (+ F7 figure).

  .venv/bin/python -m study_b.r6_review2_fixes
"""
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from study_b.r6_train import load, cols_for  # noqa: E402
from study_b.r6_parity_fixes import fit  # noqa: E402
from study_b.r6_battery_tail import PAT  # noqa: E402

OUT = Path("outputs/study_b/r6/results")
SEED = 202616
R = {}


def main() -> int:
    import pandas as pd
    from sklearn.metrics import f1_score, accuracy_score, cohen_kappa_score
    from scipy.stats import binomtest

    df, variants = load()
    cols = cols_for(df, variants["narrative_strict"])
    parity = json.load(open(OUT / "variant_results_parity.json"))
    cfg = parity["narrative_strict"]["config"]
    trval = df[df.split.isin(["train", "val"])]
    te = df[df.split == "test"]
    m_auth = fit(trval[cols], trval.label_ai, cfg)
    pred_auth = m_auth.predict(te[cols])
    base = float(f1_score(te.label_ai, pred_auth, average="macro"))
    R["faithful_baseline_check"] = round(base, 4)
    print("faithful baseline", round(base, 4), flush=True)

    # ---- M2a: entity-scan sensitivity (8.5), faithful ----------------------
    flagged = {}
    for s_ in ("gpt", "claude", "gemini", "deepseek", "kimi"):
        for l in open(f"outputs/study_b/mirrors/story_{s_}.jsonl"):
            r = json.loads(l)
            if PAT.search(r["text"]):
                flagged.setdefault(r["doc_id"], set()).add(s_)
    keep = ~te.apply(lambda r: r.source in flagged.get(r.doc_id, set()), axis=1)
    R["entity_excl_f1_faithful"] = round(float(f1_score(
        te[keep].label_ai, m_auth.predict(te[keep][cols]), average="macro")), 4)
    print("entity", R["entity_excl_f1_faithful"], flush=True)

    # ---- M2b: YC sensitivity (8.6), faithful --------------------------------
    is_yc = te.stratum.str.contains("yc", case=False, na=False)
    R["yc_sensitivity_faithful"] = {
        "yc": round(float(f1_score(te[is_yc].label_ai,
                                   m_auth.predict(te[is_yc][cols]),
                                   average="macro")), 4),
        "non_yc": round(float(f1_score(te[~is_yc].label_ai,
                                       m_auth.predict(te[~is_yc][cols]),
                                       average="macro")), 4)}
    print("yc", json.dumps(R["yc_sensitivity_faithful"]), flush=True)

    # ---- M2c: era orthogonality ablation (8.7), faithful -------------------
    from sklearn.model_selection import GroupKFold
    h = pd.read_parquet("outputs/study_b/corpus/story_human_frozen.parquet")
    year = {r.doc_id: int(str(r.snapshot_ts)[:4]) for r in h.itertuples()}
    hu = df[df.source == "human"].copy()
    hu["year"] = hu.doc_id.map(year)
    era = hu[(hu.year <= 2017) | (hu.year >= 2020)].copy()
    era["y"] = (era.year >= 2020).astype(int)
    era_gain = np.zeros(len(cols))
    for tr_i, _ in GroupKFold(n_splits=5).split(era[cols], era.y, era.domain):
        m = fit(era.iloc[tr_i][cols], era.iloc[tr_i].y, cfg)
        era_gain += m.feature_importances_
    order = np.argsort(-era_gain)
    abl = {}
    for n in (25, 50, 100):
        kc = [c for i, c in enumerate(cols) if i not in set(order[:n])]
        m2 = fit(trval[kc], trval.label_ai, cfg)
        abl[f"drop_top{n}_era_cols"] = round(float(f1_score(
            te.label_ai, m2.predict(te[kc]), average="macro")), 4)
    R["era_orthogonality_faithful"] = abl
    print("era abl", json.dumps(abl), flush=True)

    # ---- M2d: page-format / timeliness ablation (8.9), faithful ------------
    no_pag = [c for c in cols if not c.startswith("PAG_")]
    no_pag_tim = [c for c in no_pag if not c.startswith("TIM_")]
    m_np = fit(trval[no_pag], trval.label_ai, cfg)
    m_npt = fit(trval[no_pag_tim], trval.label_ai, cfg)
    R["format_ablation_faithful"] = {
        "minus_page_format": round(float(f1_score(
            te.label_ai, m_np.predict(te[no_pag]), average="macro")), 4),
        "minus_page_format_and_timeliness": round(float(f1_score(
            te.label_ai, m_npt.predict(te[no_pag_tim]), average="macro")), 4)}
    print("fmt abl", json.dumps(R["format_ablation_faithful"]), flush=True)

    # ---- M2e: format-matched humans (8.14) + pool-domain excl (8.15) -------
    art_cols = [c for c in df.columns if re.search(r"native.?article", c, re.I)]
    if art_cols:
        nc = art_cols[0]
        native_docs = set(df[(df.source == "human") & (df[nc] == 1.0)].doc_id)
        sub = df[df.doc_id.isin(native_docs)]
        stv, ste = sub[sub.split.isin(["train", "val"])], sub[sub.split == "test"]
        m3 = fit(stv[cols], stv.label_ai, cfg)
        R["format_matched_faithful"] = round(float(f1_score(
            ste.label_ai, m3.predict(ste[cols]), average="macro")), 4)
    dom_of = h.set_index("doc_id").domain.to_dict()
    pool = json.loads(Path("outputs/study_b/r3/discovery_pool.json").read_text())["doc_ids"]
    pool_domains = {dom_of[d] for d in pool if d in dom_of}
    splits = json.load(open("outputs/study_b/r6/splits.json"))
    test_domains = {d for d, s in splits["domain_split"].items() if s == "test"}
    overlap = pool_domains & test_domains
    sub = df[~df.domain.isin(overlap)]
    stv, ste = sub[sub.split.isin(["train", "val"])], sub[sub.split == "test"]
    m4 = fit(stv[cols], stv.label_ai, cfg)
    R["pool_domain_excl_faithful"] = round(float(f1_score(
        ste.label_ai, m4.predict(ste[cols]), average="macro")), 4)
    print("fmt-match/pool", R.get("format_matched_faithful"),
          R["pool_domain_excl_faithful"], flush=True)

    # ---- M2f: split-seed sensitivity (8.10), faithful ----------------------
    doc_domain = df[["doc_id", "domain"]].drop_duplicates()
    dd = dict(zip(doc_domain.doc_id, doc_domain.domain))
    by_domain = defaultdict(set)
    for d, dom in dd.items():
        by_domain[dom].add(d)
    ratios = (0.726, 0.138)
    seeds_out = {}
    for seed in (202616, 202617, 202618, 202619):
        domains = sorted(by_domain)
        random.Random(seed).shuffle(domains)
        n_docs = len(dd)
        targets = [ratios[0] * n_docs, (ratios[0] + ratios[1]) * n_docs]
        acc_n, dsplit = 0, {}
        for dom in domains:
            dsplit[dom] = ("train" if acc_n < targets[0]
                           else ("val" if acc_n < targets[1] else "test"))
            acc_n += len(by_domain[dom])
        part = df.assign(sp=df.domain.map(dsplit))
        stv = part[part.sp.isin(["train", "val"])]
        ste = part[part.sp == "test"]
        m5 = fit(stv[cols], stv.label_ai, cfg)
        p5 = m5.predict(ste[cols])
        seeds_out[str(seed)] = {
            "test_f1": round(float(f1_score(ste.label_ai, p5, average="macro")), 4),
            "test_acc": round(float(accuracy_score(ste.label_ai, p5)), 4)}
        print(f"seed {seed}", seeds_out[str(seed)], flush=True)
    R["split_seed_faithful"] = seeds_out

    # ---- M6a: error-overlap diagnostic (prereg H1' section) ----------------
    scols = cols_for(df, variants["style_only"])
    cfg_s = parity["style_only"]["config"]
    m_style = fit(trval[scols], trval.label_ai, cfg_s)
    err_n = (m_auth.predict(te[cols]) != te.label_ai).to_numpy().astype(int)
    err_s = (m_style.predict(te[scols]) != te.label_ai).to_numpy().astype(int)
    both = int((err_n & err_s).sum())
    union = int((err_n | err_s).sum())
    kappa = float(cohen_kappa_score(err_n, err_s))
    # binomial: of documents misclassified by exactly one model, is the split
    # symmetric?
    only_n, only_s = int((err_n & ~err_s.astype(bool)).sum()), int((err_s & ~err_n.astype(bool)).sum())
    bt = binomtest(only_n, only_n + only_s, 0.5)
    R["error_overlap"] = {
        "n_test": int(len(te)), "errors_narrative": int(err_n.sum()),
        "errors_style": int(err_s.sum()), "errors_both": both,
        "jaccard": round(both / union, 4) if union else None,
        "cohen_kappa": round(kappa, 4),
        "only_narrative": only_n, "only_style": only_s,
        "binomial_p": round(float(bt.pvalue), 4)}
    print("error overlap", json.dumps(R["error_overlap"]), flush=True)

    # ---- M6b: learning curve (manifest item 9) -----------------------------
    curve = {}
    docs_tv = trval.doc_id.unique()
    for frac in (0.25, 0.5, 0.75, 1.0):
        f1s = []
        for s in range(3):
            pick = set(np.random.default_rng(1000 + s).choice(
                docs_tv, size=int(frac * len(docs_tv)), replace=False))
            sub = trval[trval.doc_id.isin(pick)]
            m6 = fit(sub[cols], sub.label_ai, cfg)
            f1s.append(float(f1_score(te.label_ai, m6.predict(te[cols]),
                                      average="macro")))
        curve[str(frac)] = {"mean_f1": round(float(np.mean(f1s)), 4),
                            "range": [round(min(f1s), 4), round(max(f1s), 4)]}
        print("curve", frac, curve[str(frac)], flush=True)
    R["learning_curve"] = curve

    # ---- m7: faithful 6-way accuracy ---------------------------------------
    import xgboost as xgb
    cfg6 = json.load(open(OUT / "parity_fixes.json"))[
        "p2_core_fingerprint"]["sixway_config"]
    src_order = ["human", "gpt", "claude", "gemini", "deepseek", "kimi"]
    ymap = {s: i for i, s in enumerate(src_order)}
    m6w = xgb.XGBClassifier(random_state=SEED, n_jobs=-1, tree_method="hist",
                            eval_metric="mlogloss", **cfg6)
    m6w.fit(trval[cols], trval.source.map(ymap))
    p6 = m6w.predict(te[cols])
    R["sixway_faithful"] = {
        "test_macro_f1": round(float(f1_score(te.source.map(ymap), p6,
                                              average="macro")), 4),
        "test_acc": round(float(accuracy_score(te.source.map(ymap), p6)), 4)}
    print("6way", json.dumps(R["sixway_faithful"]), flush=True)

    # ---- m17: geometry extras ----------------------------------------------
    X = np.nan_to_num(df[cols].to_numpy(dtype=np.float32), nan=0.0)
    mu, sd = X.mean(0), X.std(0); sd[sd == 0] = 1
    Xz = (X - mu) / sd
    hm = (df.source == "human").to_numpy()
    from sklearn.neighbors import NearestNeighbors
    def r10(A):
        nn = NearestNeighbors(n_neighbors=11).fit(A)
        d, _ = nn.kneighbors(A)
        return float(d[:, 1:].mean())
    rng = np.random.default_rng(SEED)
    hidx = rng.choice(np.where(hm)[0], 1500, replace=False)
    aidx = rng.choice(np.where(~hm)[0], 1500, replace=False)
    R["geometry_extras"] = {
        "mean_10nn_radius_human": round(r10(Xz[hidx]), 3),
        "mean_10nn_radius_ai": round(r10(Xz[aidx]), 3)}
    R["geometry_extras"]["radius_ratio"] = round(
        R["geometry_extras"]["mean_10nn_radius_human"]
        / R["geometry_extras"]["mean_10nn_radius_ai"], 3)
    print("geometry", json.dumps(R["geometry_extras"]), flush=True)

    # ---- m8: repeatability mean pairwise Cohen kappa -----------------------
    runs = []
    for i in range(1, 6):
        d = {}
        for l in open(f"outputs/study_b/r5/answers_repeat_{i}.jsonl"):
            r = json.loads(l)
            for fid, ans in (r.get("answers") or {}).items():
                d[(r.get("doc_id"), r.get("source"), fid)] = str(ans)
        runs.append(d)
    common = set(runs[0])
    for d in runs[1:]:
        common &= set(d)
    common = sorted(common)
    ks = []
    for i in range(5):
        for j in range(i + 1, 5):
            a = [runs[i][k] for k in common]
            b = [runs[j][k] for k in common]
            ks.append(cohen_kappa_score(a, b))
    R["repeat_pairwise_kappa"] = {"mean": round(float(np.mean(ks)), 4),
                                  "n_items": len(common)}
    print("kappa", json.dumps(R["repeat_pairwise_kappa"]), flush=True)

    # ---- m19: F7 length boxplots -------------------------------------------
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from study_b.r6_figures_final import (HUMAN, AI_FILL, INK, SHORT, ORDER,
                                          style, save, CAPTIONS, FIG)
    hw = {r.doc_id: len(str(r.story_human).split()) for r in h.itertuples()}
    lengths = {"human": list(hw.values())}
    for s_ in ("gpt", "claude", "gemini", "deepseek", "kimi"):
        lengths[s_] = [len(json.loads(l)["text"].split())
                       for l in open(f"outputs/study_b/mirrors/story_{s_}.jsonl")]
    fig, ax = plt.subplots(figsize=(8.6, 4.4), dpi=160)
    bp = ax.boxplot([lengths[s] for s in ORDER], showfliers=False,
                    patch_artist=True, widths=0.55, medianprops=dict(color=INK))
    for patch, s_ in zip(bp["boxes"], ORDER):
        patch.set_facecolor(HUMAN if s_ == "human" else AI_FILL)
        patch.set_edgecolor(INK)
    ax.set_xticklabels([SHORT[s] for s in ORDER], fontsize=9.5)
    ax.set_ylabel("Words per document", fontsize=10.5, color=INK)
    style(ax)
    ax.set_title("Document length by source", fontsize=12, color=INK, pad=10)
    save(fig, "f7_lengths",
         "Word-count distributions by source (boxes = IQR, whiskers to 1.5 "
         "IQR, outliers hidden). Mirrors run longer than their human sources "
         "(disclosed as R3); the length-matched sensitivity (8.4) and the "
         "failing length-only baseline (6.1b) bound this confound.")
    plt.close(fig)
    caps = FIG / "CAPTIONS.md"
    if caps.exists() and "f7_lengths" not in caps.read_text():
        caps.write_text(caps.read_text() +
                        f"\n**f7_lengths**: {CAPTIONS['f7_lengths']}\n")

    json.dump(R, open(OUT / "review2_fixes.json", "w"), indent=2)
    print("REVIEW2 FIXES DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
