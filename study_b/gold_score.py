#!/usr/bin/env python
"""Gold session (draw 1) scoring: human-human and human-model agreement.

Items are (feature, post) cells of the draw's features that belong to the
final instrument (outputs/study_b/r6/variant_sets.json, all_features) on its
12 posts; a cell answered "unclear - none of these fits" by either annotator
is excluded. Each kappa is Cohen's kappa on the pooled item-level
contingency over all scored items (answer labels pooled across features).

Inputs (gated): outputs/study_b/gold/draw_1/DRAW_MANIFEST.json,
annotations_final.json (the two annotator tabs of the session sheet),
model_answer_key.xlsx. Writes the answer_validation block of
outputs/study_b/gold/draw_1/GOLD_RESULTS.json; the style-boundary audit block
is the session record and is kept as is.

  .venv/bin/python -m study_b.gold_score
"""
import json
import sys
from pathlib import Path

G = Path("outputs/study_b/gold/draw_1")
R6 = Path("outputs/study_b/r6")
ORIGINAL = {"a1_model": [91.67, 0.9056], "a2_model": [79.86, 0.7724],
            "mean_hm_kappa": 0.839, "human_human": [76.85, 0.739]}


def main() -> int:
    import pandas as pd
    from sklearn.metrics import cohen_kappa_score
    draw = json.load(open(G / "DRAW_MANIFEST.json"))
    ann = json.load(open(G / "annotations_final.json"))
    key = pd.read_excel(G / "model_answer_key.xlsx", sheet_name="Model - Answers")
    model = {r["Q#"]: [str(r[f"POST {i}"]) for i in range(1, 13)]
             for _, r in key.iterrows()}
    instrument = set(json.load(open(R6 / "variant_sets.json"))["all_features"])
    qids = {f"Q{i + 1:02d}": f["id"] for i, f in enumerate(draw["features"])
            if f["id"] in instrument}
    items, unclear = [], 0
    for q in qids:
        for i in range(12):
            a, b, m = ann["A"][q][i], ann["B"][q][i], model[q][i]
            if "unclear" in a or "unclear" in b:
                unclear += 1
                continue
            items.append((a, b, m))
    A, B, M = (list(x) for x in zip(*items))

    def pair(x, y):
        return {"agreement_pct": round(100 * sum(i == j for i, j in zip(x, y))
                                       / len(x), 2),
                "kappa": round(float(cohen_kappa_score(x, y)), 4)}

    av = {"features_scored": len(qids), "items_total": 12 * len(qids),
          "items_scored": len(items), "unclear_flags": unclear,
          "human_human": pair(A, B), "annotatorA_model": pair(A, M),
          "annotatorB_model": pair(B, M)}
    av["mean_human_model_kappa"] = round(
        (av["annotatorA_model"]["kappa"] + av["annotatorB_model"]["kappa"]) / 2, 4)
    av["bars_filed"] = {"human_human": 0.6, "extractor_vs_consensus": 0.6}
    av["original"] = ORIGINAL
    rec = json.load(open(G / "GOLD_RESULTS.json"))
    rec["note"] = ("Gold session scored on the final annotations, over the "
                   "draw features in the final instrument (study_b/gold_score.py)")
    rec["answer_validation"] = av
    json.dump(rec, open(G / "GOLD_RESULTS.json", "w"), indent=1)
    print(json.dumps(av, indent=1), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
