#!/usr/bin/env python
"""Review quick-win batch (C3, C6, C8, C12): format audit, pool-domain overlap,
n-gram memorization, geometry, vertical Kruskal-Wallis, mirror adherence.

All outputs -> outputs/study_b/r6/results/review_batch.json (+ LDA figure F5).

  .venv/bin/python -m study_b.r6_review_batch
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from study_b.r6_train import load, cols_for, fit  # noqa: E402

OUT = Path("outputs/study_b/r6/results")
SEED = 202616
R = {}


def main() -> int:
    import pandas as pd
    from sklearn.metrics import f1_score

    df, variants = load()
    cols = cols_for(df, variants["narrative_strict"])
    cfg = json.load(open(OUT / "variant_results.json"))["narrative_strict"]["config"]

    # ---------- C3: format audit --------------------------------------------
    # simpler robust approach: use template answers for content_format-like
    # features via encoded columns whose name mentions article/transcript
    art_cols = [c for c in df.columns if re.search(
        r"(native.?article|transcript|webinar|roundup|interview|archive|excerpt|landing)",
        c, re.I)]
    fmt_summary = {}
    for c in art_cols[:12]:
        by = df.groupby("source")[c].mean().round(3).to_dict()
        fmt_summary[c] = by
    R["format_audit_columns"] = fmt_summary
    # native-article human subset: humans whose page_type one-hot for native
    # article is 1 (find the column)
    native_cols = [c for c in df.columns if re.search(r"native.?article", c, re.I)]
    if native_cols:
        nc = native_cols[0]
        native_docs = set(df[(df.source == "human") & (df[nc] == 1.0)].doc_id)
        sub = df[df.doc_id.isin(native_docs)]
        tr, te = sub[sub.split == "train"], sub[sub.split == "test"]
        m = fit(tr[cols], tr.label_ai, cfg)
        f1 = f1_score(te.label_ai, m.predict(te[cols]), average="macro")
        R["format_matched_headline"] = {
            "native_article_human_docs": len(native_docs),
            "share_of_humans": round(len(native_docs) / df[df.source == "human"].doc_id.nunique(), 3),
            "test_macro_f1": round(float(f1), 4), "test_n": len(te)}
    print("C3:", json.dumps(R.get("format_matched_headline", fmt_summary)), flush=True)

    # ---------- C6: discovery-pool domains vs holdout ------------------------
    h = pd.read_parquet("outputs/study_b/corpus/story_human_frozen.parquet")
    dom_of = h.set_index("doc_id").domain.to_dict()
    pool = json.loads(Path("outputs/study_b/r3/discovery_pool.json").read_text())["doc_ids"]
    pool_domains = {dom_of[d] for d in pool if d in dom_of}
    splits = json.load(open("outputs/study_b/r6/splits.json"))
    test_domains = {dom for dom, s in splits["domain_split"].items() if s == "test"}
    overlap = sorted(pool_domains & test_domains)
    R["pool_domain_overlap"] = {"pool_domains": len(pool_domains),
                                "test_domains": len(test_domains),
                                "overlap": len(overlap), "overlap_list": overlap}
    if overlap:
        keep = ~df.domain.isin(overlap)
        sub = df[keep]
        tr, te = sub[sub.split == "train"], sub[sub.split == "test"]
        m = fit(tr[cols], tr.label_ai, cfg)
        f1 = f1_score(te.label_ai, m.predict(te[cols]), average="macro")
        R["pool_domain_overlap"]["sensitivity_test_f1_excl"] = round(float(f1), 4)
    print("C6:", json.dumps(R["pool_domain_overlap"]["overlap"]), flush=True)

    # ---------- C8: 13-gram memorization scan --------------------------------
    def grams(text, n=13):
        toks = text.lower().split()
        return {" ".join(toks[i:i + n]) for i in range(0, max(0, len(toks) - n + 1), 3)}
    hum_text = h.set_index("doc_id").story_human.to_dict()
    per_model = {}
    worst = []
    for s_ in ("gpt", "claude", "gemini", "deepseek", "kimi"):
        n_flag = tot = 0
        for l in open(f"outputs/study_b/mirrors/story_{s_}.jsonl"):
            r = json.loads(l)
            tot += 1
            ht = hum_text.get(r["doc_id"])
            if not ht:
                continue
            ov = grams(r["text"]) & grams(ht, 13)
            if ov:
                n_flag += 1
                worst.append((s_, r["doc_id"], len(ov)))
        per_model[s_] = {"flagged": n_flag, "total": tot,
                        "rate": round(n_flag / tot, 4)}
    R["ngram_memorization"] = {"per_model": per_model,
        "pooled_rate": round(sum(p["flagged"] for p in per_model.values())
                             / sum(p["total"] for p in per_model.values()), 4),
        "v1_reference": 0.005}
    print("C8:", json.dumps(R["ngram_memorization"]["pooled_rate"]), flush=True)

    # ---------- C12: geometry, KW over verticals, mirror adherence, LDA ------
    X = df[cols].to_numpy(dtype=np.float32)
    X = np.nan_to_num(X, nan=0.0)
    mu, sd = X.mean(0), X.std(0); sd[sd == 0] = 1
    Xz = (X - mu) / sd
    hm = (df.source == "human").to_numpy()
    c_h, c_a = Xz[hm].mean(0), Xz[~hm].mean(0)
    disp_h = float(np.linalg.norm(Xz[hm] - c_h, axis=1).mean())
    disp_a = float(np.linalg.norm(Xz[~hm] - c_a, axis=1).mean())
    centroid_dist = float(np.linalg.norm(c_h - c_a))
    R["geometry"] = {"centroid_distance": round(centroid_dist, 3),
                     "dispersion_human": round(disp_h, 3),
                     "dispersion_ai": round(disp_a, 3),
                     "dispersion_ratio": round(disp_h / disp_a, 3)}
    # Kruskal-Wallis: does headline accuracy differ across verticals? Use
    # per-doc correctness of the frozen headline model on test
    from scipy.stats import kruskal
    tr, te = df[df.split == "train"], df[df.split == "test"]
    m = fit(tr[cols], tr.label_ai, cfg)
    correct = (m.predict(te[cols]) == te.label_ai).astype(int)
    groups = [correct[(te.vertical == v).to_numpy()] for v in te.vertical.unique()
              if (te.vertical == v).sum() >= 20]
    kw = kruskal(*groups)
    R["vertical_kruskal_wallis"] = {"H": round(float(kw.statistic), 3),
                                    "p": round(float(kw.pvalue), 4),
                                    "n_groups": len(groups)}
    # mirror adherence: share of mirrors within 10% of the human length
    hw = h.set_index("doc_id").words.to_dict()
    adh = {}
    for s_ in ("gpt", "claude", "gemini", "deepseek", "kimi"):
        ok = tot = 0
        for l in open(f"outputs/study_b/mirrors/story_{s_}.jsonl"):
            r = json.loads(l)
            tw = hw.get(r["doc_id"])
            if tw:
                tot += 1
                ok += abs(len(r["text"].split()) - tw) <= 0.10 * tw
        adh[s_] = round(ok / tot, 3)
    R["mirror_length_adherence_10pct"] = adh
    # F5: LDA projection
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    lda = LinearDiscriminantAnalysis(n_components=2)
    Z = lda.fit_transform(Xz, df.source)
    fig, ax = plt.subplots(figsize=(7.5, 6), dpi=160)
    colors = {"human": "#3b5bdb", "gpt": "#e8590c", "claude": "#f08c00",
              "gemini": "#2f9e44", "deepseek": "#9c36b5", "kimi": "#868e96"}
    for s_ in ["gpt", "claude", "gemini", "deepseek", "kimi", "human"]:
        mk = (df.source == s_).to_numpy()
        ax.scatter(Z[mk, 0], Z[mk, 1], s=4, alpha=0.35, c=colors[s_], label=s_)
    ax.legend(markerscale=3, fontsize=9)
    ax.set_title("LDA projection of the narrative-strict feature space")
    ax.set_xlabel("LD1"); ax.set_ylabel("LD2")
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    plt.savefig(OUT / "figures" / "fig_lda.png"); plt.close()
    print("C12:", json.dumps({k: R[k] for k in ("geometry", "vertical_kruskal_wallis",
                                                "mirror_length_adherence_10pct")}), flush=True)

    json.dump(R, open(OUT / "review_batch.json", "w"), indent=2)
    print("review batch written", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
