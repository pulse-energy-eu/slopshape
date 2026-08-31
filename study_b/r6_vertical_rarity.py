#!/usr/bin/env python
"""S8 gap-fill batch (PI decisions 2026-08-20): battery 8.18 under the
faithful protocol + T10 rarity tail composition.

8.18: the review-batch Kruskal-Wallis (H=11.4, p=0.044) was fit on train
only and never saved per-vertical values. This recomputes it under the
faithful protocol (final refit on train+val, parity config from
variant_results_parity.json) and writes the per-vertical macro-F1 table.
The refit must reproduce the committed headline (0.9803) exactly or the
script aborts - no new number is derived from a model that does not match
the frozen record.

T10: tail composition (rarest 1/5/10%) by source from the frozen per-doc
rarity.parquet (train+val percentile reference), on BOTH the full-corpus
basis (the frozen headline rarity stats' basis) and the test-only basis
(the original Table 12's basis). Pure groupby, no modeling.

Output -> outputs/study_b/r6/results/vertical_rarity_faithful.json

  .venv/bin/python -m study_b.r6_vertical_rarity
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from study_b.r6_train import load, cols_for  # noqa: E402

OUT = Path("outputs/study_b/r6/results")
SEED = 202616
HEADLINE_F1 = 0.9803  # committed faithful headline; refit must reproduce it


def fit(X, y, cfg):
    import xgboost as xgb
    return xgb.XGBClassifier(random_state=SEED, n_jobs=-1, tree_method="hist",
                             eval_metric="logloss", **cfg).fit(X, y)


def main() -> int:
    import numpy as np
    import pandas as pd
    from scipy.stats import kruskal
    from sklearn.metrics import f1_score

    R = {}

    # ---------------- 8.18 faithful: vertical KW + per-vertical F1 ----------
    df, variants = load()
    cols = cols_for(df, variants["narrative_strict"])
    cfg = json.load(open(OUT / "variant_results_parity.json"))[
        "narrative_strict"]["config"]
    trval = df[df.split.isin(["train", "val"])]
    te = df[df.split == "test"].reset_index(drop=True)
    m = fit(trval[cols], trval.label_ai, cfg)
    pred = m.predict(te[cols])
    f1 = round(float(f1_score(te.label_ai, pred, average="macro")), 4)
    assert f1 == HEADLINE_F1, f"refit {f1} != committed headline {HEADLINE_F1}"
    correct = (pred == te.label_ai).astype(int)

    per_vertical = {}
    groups = []
    for v in sorted(te.vertical.unique()):
        mk = (te.vertical == v).to_numpy()
        if mk.sum() < 20:  # same >=20-test-docs rule as the review batch
            continue
        groups.append(correct[mk])
        per_vertical[v] = {
            "n_test_docs": int(mk.sum()),
            "macro_f1": round(float(f1_score(
                te.label_ai[mk], pred[mk], average="macro")), 4),
            "accuracy": round(float(correct[mk].mean()), 4)}
    kw = kruskal(*groups)
    f1s = [d["macro_f1"] for d in per_vertical.values()]
    R["vertical_faithful"] = {
        "protocol": "faithful (final refit on train+val, parity config)",
        "headline_reproduced": f1,
        "kruskal_wallis": {"H": round(float(kw.statistic), 3),
                           "p": round(float(kw.pvalue), 4),
                           "n_groups": len(groups)},
        "per_vertical": per_vertical,
        "f1_range": [min(f1s), max(f1s)],
        "train_only_reference": {"H": 11.4, "p": 0.044, "n_groups": 6,
                                 "source": "review_batch.json (superseded)"}}
    print("8.18 faithful:", json.dumps(R["vertical_faithful"]["kruskal_wallis"]),
          "range", R["vertical_faithful"]["f1_range"], flush=True)

    # ---------------- T10: rarity tail composition ---------------------------
    rar = pd.read_parquet(OUT / "rarity" / "rarity.parquet")
    tails = {}
    for basis in ("full_corpus", "test_only"):
        sub = rar if basis == "full_corpus" else rar[rar.split == "test"]
        tails[basis] = {"n_docs": len(sub)}
        for name, thr in (("rarest_1pct", 0.99), ("rarest_5pct", 0.95),
                          ("rarest_10pct", 0.90)):
            tail = sub[sub.rarity_trainval >= thr]
            by = tail.source.value_counts().to_dict()
            n_h = by.get("human", 0)
            n_ai = int(sum(v for k, v in by.items() if k != "human"))
            tails[basis][name] = {
                "counts_by_source": {s: int(by.get(s, 0)) for s in
                                     ("human", "deepseek", "claude", "gemini",
                                      "kimi", "gpt")},
                "tail_n": len(tail),
                "human_share_of_tail": round(n_h / max(1, len(tail)), 4),
                "human_vs_ai_counts": [n_h, n_ai]}
    R["rarity_tails"] = {
        "reference": "train+val percentile basis (rarity_trainval)",
        "note": ("full_corpus matches the frozen headline rarity stats' basis; "
                 "test_only mirrors the original Table 12's basis"),
        **tails}
    print("T10 tails full_corpus:", json.dumps(tails["full_corpus"]), flush=True)
    print("T10 tails test_only:", json.dumps(tails["test_only"]), flush=True)

    json.dump(R, open(OUT / "vertical_rarity_faithful.json", "w"), indent=2)
    print("written:", OUT / "vertical_rarity_faithful.json", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
