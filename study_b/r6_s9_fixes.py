#!/usr/bin/env python
"""S9 review-fix batch (PI approvals 2026-08-20, FEEDBACK_V0 items 9-11, 18,
20, 21): the analyses whose executed code did not match the paper's stated
spec, rerun to spec, plus the pre-registered statistics that were committed
but never delivered.

a. H1' pre-registered package: narrative-minus-style delta with BOTH
   prompt-level and DOMAIN-CLUSTER bootstrap CIs (cluster primary, per the
   prereg), document-level McNemar, two-sided sensitivity p.
b. GRID sensitivity row: the original's published constants untuned
   (binary 420/8/2.0/5; six-way 500/7/1.0), finals on train+val.
c. TF-IDF baseline at the ORIGINAL's spec: 5,000 features, word 1-2 grams,
   the full 108-config sweep on val, final on train+val (replaces the
   50,000-feature fixed-config run).
d. Stylometric + length baselines refit with finals on train+val (sweep for
   stylometric) so Table 7's protocol caption is true.
e. Memorization rules run EXACTLY: all 13-grams (no stride sampling) with a
   shuffled-human control, and the near-verbatim rule with the original's
   third conjunct (longest common span >= 30 tokens); filtered-headline
   recheck.
f. Battery 8.4 rebuilt: decile-stratified length matching (script was lost),
   frozen faithful headline evaluated on the matched subset, rarity d, corr,
   and PER-MODEL matched rarity means.

Every classifier refit asserts the committed faithful headline (0.9803)
before any new number is derived.

Output -> outputs/study_b/r6/results/s9_fixes.json

  .venv/bin/python -m study_b.r6_s9_fixes
"""
import json
import sys
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from study_b.r6_train import load, cols_for  # noqa: E402
from study_b.r6_baselines import load_texts, stylometrics  # noqa: E402

OUT = Path("outputs/study_b/r6/results")
SEED = 202616
HEADLINE_F1 = 0.9803
STYLE_F1 = 0.8811
GRID_BIN = {"n_estimators": [210, 420, 840], "max_depth": [4, 8, 12],
            "reg_lambda": [1.0, 2.0, 4.0],
            "scale_pos_weight": [1.0, 2.5, 5.0, 7.5]}
N_BOOT = 10_000


def fit(X, y, cfg, num_class=None):
    import xgboost as xgb
    kw = dict(random_state=SEED, n_jobs=-1, tree_method="hist", **cfg)
    if num_class:
        return xgb.XGBClassifier(eval_metric="mlogloss", **kw).fit(X, y)
    return xgb.XGBClassifier(eval_metric="logloss", **kw).fit(X, y)


def macro_f1(y, p):
    from sklearn.metrics import f1_score
    return float(f1_score(y, p, average="macro"))


def boot_delta_ci(te, err_a, err_b, unit_col, rng):
    """Bootstrap CI on macro-F1(model A) - macro-F1(model B), resampling units."""
    units = te[unit_col].unique()
    idx_by_unit = {u: np.where((te[unit_col] == u).to_numpy())[0] for u in units}
    y = te.label_ai.to_numpy()
    pa, pb = err_a, err_b  # predictions
    deltas = np.empty(N_BOOT)
    for b in range(N_BOOT):
        pick = rng.choice(units, size=len(units), replace=True)
        ii = np.concatenate([idx_by_unit[u] for u in pick])
        deltas[b] = macro_f1(y[ii], pa[ii]) - macro_f1(y[ii], pb[ii])
    return deltas


def main() -> int:
    import pandas as pd
    from scipy.stats import binomtest
    from sklearn.metrics import average_precision_score, accuracy_score
    R = {}

    df, variants = load()
    parity = json.load(open(OUT / "variant_results_parity.json"))
    cols_n = cols_for(df, variants["narrative_strict"])
    cols_s = cols_for(df, variants["style_only"])
    trval = df[df.split.isin(["train", "val"])]
    te = df[df.split == "test"].reset_index(drop=True)

    # domain map (features_encoded may not carry domain)
    h = pd.read_parquet("outputs/study_b/corpus/story_human_frozen.parquet")
    dom = h.set_index("doc_id").domain.to_dict()
    te = te.assign(domain=te.doc_id.map(dom))
    assert te.domain.notna().all()

    m_head = fit(trval[cols_n], trval.label_ai, parity["narrative_strict"]["config"])
    pred_n = m_head.predict(te[cols_n])
    f1_head = round(macro_f1(te.label_ai, pred_n), 4)
    assert f1_head == HEADLINE_F1, f"headline refit {f1_head} != {HEADLINE_F1}"
    m_style = fit(trval[cols_s], trval.label_ai, parity["style_only"]["config"])
    pred_s = m_style.predict(te[cols_s])
    f1_style = round(macro_f1(te.label_ai, pred_s), 4)
    assert f1_style == STYLE_F1, f"style refit {f1_style} != {STYLE_F1}"

    # ---------------- a. H1' pre-registered package --------------------------
    rng = np.random.default_rng(SEED)
    d_prompt = boot_delta_ci(te, pred_n, pred_s, "doc_id", rng)
    d_domain = boot_delta_ci(te, pred_n, pred_s, "domain", rng)
    ok_n = pred_n == te.label_ai.to_numpy()
    ok_s = pred_s == te.label_ai.to_numpy()
    b_disc = int((~ok_n & ok_s).sum())   # narrative wrong, style right
    c_disc = int((ok_n & ~ok_s).sum())   # narrative right, style wrong
    mcn = binomtest(min(b_disc, c_disc), b_disc + c_disc, 0.5).pvalue
    R["h1_prereg_package"] = {
        "delta_point_pts": round((macro_f1(te.label_ai, pred_n)
                                  - macro_f1(te.label_ai, pred_s)) * 100, 1),
        "prompt_ci_pts": [round(float(np.percentile(d_prompt, 2.5)) * 100, 1),
                          round(float(np.percentile(d_prompt, 97.5)) * 100, 1)],
        "domain_cluster_ci_pts": [round(float(np.percentile(d_domain, 2.5)) * 100, 1),
                                  round(float(np.percentile(d_domain, 97.5)) * 100, 1)],
        "mcnemar_discordant": [b_disc, c_disc],
        "mcnemar_two_sided_p": float(f"{mcn:.3g}"),
        "boot_two_sided_p_domain": round(2 * min((d_domain <= 0).mean(),
                                                 (d_domain >= 0).mean()), 6),
        "note": "domain-cluster CI primary per prereg; 10k resamples seed 202616"}
    print("a:", json.dumps(R["h1_prereg_package"]), flush=True)

    # ---------------- b. GRID sensitivity: original constants ----------------
    m_oc = fit(trval[cols_n], trval.label_ai,
               {"n_estimators": 420, "max_depth": 8, "reg_lambda": 2.0,
                "scale_pos_weight": 5.0})
    p_oc = m_oc.predict(te[cols_n])
    y6, src_order = pd.factorize(df.source)
    trv6 = df.split.isin(["train", "val"]).to_numpy()
    te6 = (df.split == "test").to_numpy()
    m6 = fit(df[trv6][cols_n], y6[trv6],
             {"n_estimators": 500, "max_depth": 7, "reg_lambda": 1.0},
             num_class=6)
    p6 = m6.predict(df[te6][cols_n])
    R["original_constants_sensitivity"] = {
        "binary_test_macro_f1": round(macro_f1(te.label_ai, p_oc), 4),
        "binary_auprc": round(float(average_precision_score(
            te.label_ai, m_oc.predict_proba(te[cols_n])[:, 1])), 4),
        "sixway_test_macro_f1": round(macro_f1(y6[te6], p6), 4),
        "sixway_test_acc": round(float(accuracy_score(y6[te6], p6)), 4)}
    print("b:", json.dumps(R["original_constants_sensitivity"]), flush=True)

    # ---------------- c+d. baselines to spec, finals on train+val ------------
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    texts = load_texts()
    texts = texts.merge(df[["doc_id", "source"]].drop_duplicates().assign(_in=1),
                        on=["doc_id", "source"], how="inner")
    tr_m = (texts.split == "train").to_numpy()
    va_m = (texts.split == "val").to_numpy()
    tv_m = (texts.split.isin(["train", "val"])).to_numpy()
    tt_m = (texts.split == "test").to_numpy()
    y = texts.y.to_numpy()

    def sweep_final(Xtr, ytr, Xva, yva, Xtv, ytv, Xte):
        import itertools
        best, best_cfg = -1.0, None
        for vals in itertools.product(*GRID_BIN.values()):
            cfg = dict(zip(GRID_BIN.keys(), vals))
            m = fit(Xtr, ytr, cfg)
            f1 = macro_f1(yva, m.predict(Xva))
            if f1 > best:
                best, best_cfg = f1, cfg
        m = fit(Xtv, ytv, best_cfg)
        return m, best_cfg, m.predict(Xte), m.predict_proba(Xte)[:, 1]

    vec = TfidfVectorizer(ngram_range=(1, 2), max_features=5000)
    Xall = vec.fit_transform(texts.text)
    _, cfg_tfidf, p_tf, pr_tf = sweep_final(
        Xall[tr_m], y[tr_m], Xall[va_m], y[va_m], Xall[tv_m], y[tv_m], Xall[tt_m])
    R["tfidf_original_spec"] = {
        "max_features": 5000, "config": cfg_tfidf,
        "test_macro_f1": round(macro_f1(y[tt_m], p_tf), 4),
        "auprc": round(float(average_precision_score(y[tt_m], pr_tf)), 4),
        "final_fit": "train+val"}
    print("c:", json.dumps(R["tfidf_original_spec"]), flush=True)

    Xsty = np.asarray(stylometrics(texts.text.tolist()), dtype=np.float32)
    _, cfg_sty, p_sty, pr_sty = sweep_final(
        Xsty[tr_m], y[tr_m], Xsty[va_m], y[va_m], Xsty[tv_m], y[tv_m], Xsty[tt_m])
    words = texts.text.str.split().str.len().to_numpy().reshape(-1, 1)
    lg = LogisticRegression(max_iter=1000).fit(words[tv_m], y[tv_m])
    R["stylometric_trainval"] = {
        "config": cfg_sty,
        "test_macro_f1": round(macro_f1(y[tt_m], p_sty), 4),
        "auprc": round(float(average_precision_score(y[tt_m], pr_sty)), 4),
        "final_fit": "train+val"}
    R["length_only_trainval"] = {
        "test_macro_f1": round(macro_f1(y[tt_m], lg.predict(words[tt_m])), 4),
        "auprc": round(float(average_precision_score(
            y[tt_m], lg.predict_proba(words[tt_m])[:, 1])), 4),
        "final_fit": "train+val"}
    print("d:", json.dumps({**R["stylometric_trainval"],
                            "length": R["length_only_trainval"]}), flush=True)

    # ---------------- e. exact memorization rules ----------------------------
    def grams(toks, n):
        return set(zip(*[toks[i:] for i in range(n)]))
    tok = {(r.doc_id, r.source): r.text.lower().split()
           for r in texts.itertuples()}
    humans = {d: t for (d, s), t in tok.items() if s == "human"}
    rng_m = np.random.default_rng(SEED)
    hum_ids = sorted(humans)
    flag13, flag_nv, per_model = set(), set(), {}
    ctrl_hits = ctrl_n = 0
    for (d, s), t in tok.items():
        if s == "human" or d not in humans:
            continue
        ht = humans[d]
        g13 = grams(ht, 13) & grams(t, 13)
        hit13 = len(g13) > 0
        per_model.setdefault(s, [0, 0])
        per_model[s][1] += 1
        if hit13:
            per_model[s][0] += 1
            flag13.add(d)
        g8h, g8m = grams(ht, 8), grams(t, 8)
        shared8 = g8h & g8m
        cov = max(len(shared8) / max(1, len(g8h)),
                  len(shared8) / max(1, len(g8m)))
        if cov >= 0.05 and len(shared8) >= 4:
            span = SequenceMatcher(None, ht, t, autojunk=False)\
                .find_longest_match(0, len(ht), 0, len(t)).size
            if span >= 30:
                flag_nv.add(d)
        # shuffled-human control: same mirror vs a random OTHER human doc
        od = hum_ids[rng_m.integers(len(hum_ids))]
        if od != d:
            ctrl_n += 1
            ctrl_hits += bool(grams(humans[od], 13) & grams(t, 13))
    n_pairs = sum(v[1] for v in per_model.values())
    flagged = flag13 | flag_nv
    keep = ~df.doc_id.isin(flagged)
    trval_f = df[keep & df.split.isin(["train", "val"])]
    te_f = df[keep & (df.split == "test")]
    m_f = fit(trval_f[cols_n], trval_f.label_ai, parity["narrative_strict"]["config"])
    R["memorization_exact"] = {
        "pairs": n_pairs,
        "flagged_13gram_pairs": sum(v[0] for v in per_model.values()),
        "rate_13gram": round(sum(v[0] for v in per_model.values()) / n_pairs, 4),
        "per_model_13gram": {s: {"flagged": v[0], "rate": round(v[0] / v[1], 4)}
                             for s, v in sorted(per_model.items())},
        "shuffled_control_rate": round(ctrl_hits / max(1, ctrl_n), 4),
        "near_verbatim_pairs": len(flag_nv),
        "prompts_excluded": len(flagged),
        "filtered_headline_macro_f1": round(macro_f1(
            te_f.label_ai, m_f.predict(te_f[cols_n])), 4),
        "note": "exact rules: all 13-grams (no stride sampling); near-verbatim "
                "= max-direction 8-gram coverage >=5% AND >=4 distinct 8-grams "
                "AND longest common span >=30 tokens"}
    print("e:", json.dumps(R["memorization_exact"]), flush=True)

    # ---------------- f. battery 8.4 faithful rebuild ------------------------
    w_by = {(r.doc_id, r.source): len(r.text.split()) for r in texts.itertuples()}
    te_w = te.assign(words=[w_by[(r.doc_id, r.source)] for r in te.itertuples()])
    hw = te_w[te_w.source == "human"].words.to_numpy()
    edges = np.quantile(hw, np.linspace(0, 1, 11))
    edges[0], edges[-1] = -np.inf, np.inf
    rng_f = np.random.default_rng(SEED)
    matched_idx = list(te_w.index[te_w.source == "human"])
    for b in range(10):
        lo, hi = edges[b], edges[b + 1]
        h_n = int(((te_w.source == "human") & (te_w.words >= lo)
                   & (te_w.words < hi)).sum())
        ai_pool = te_w.index[(te_w.source != "human") & (te_w.words >= lo)
                             & (te_w.words < hi)].to_numpy()
        take = min(len(ai_pool), 5 * h_n)
        matched_idx += list(rng_f.choice(ai_pool, size=take, replace=False))
    sub = te_w.loc[sorted(matched_idx)]
    rar = pd.read_parquet(OUT / "rarity" / "rarity.parquet")
    key = sub[["doc_id", "source"]].merge(rar, on=["doc_id", "source"])
    hum_r = key[key.source == "human"].rarity_trainval.to_numpy()
    ai_r = key[key.source != "human"].rarity_trainval.to_numpy()
    pooled = np.sqrt((hum_r.std() ** 2 + ai_r.std() ** 2) / 2)
    sub_w = sub.merge(rar, on=["doc_id", "source"])
    R["length_matched_faithful"] = {
        "matched_n": len(sub),
        "median_words_human": float(np.median(sub[sub.source == "human"].words)),
        "median_words_ai": float(np.median(sub[sub.source != "human"].words)),
        "test_macro_f1": round(macro_f1(sub.label_ai,
                                        m_head.predict(sub[cols_n])), 4),
        "rarity_d": round(float((hum_r.mean() - ai_r.mean()) / pooled), 2),
        "corr_words_rarity": round(float(np.corrcoef(
            sub_w.words, sub_w.rarity_trainval)[0, 1]), 3),
        "per_model_matched_rarity_mean": {
            s: round(float(key[key.source == s].rarity_trainval.mean()), 3)
            for s in ["deepseek", "claude", "gemini", "kimi", "gpt"]},
        "protocol": "faithful (frozen train+val headline evaluated on the "
                    "decile-matched test subset; seed 202616)"}
    print("f:", json.dumps(R["length_matched_faithful"]), flush=True)

    json.dump(R, open(OUT / "s9_fixes.json", "w"), indent=2)
    print("written:", OUT / "s9_fixes.json", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
