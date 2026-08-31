#!/usr/bin/env python
"""R7 durability evaluation: the rewording-attack result (paper Section 5.5).

Attacked test set = the 290 unchanged human test posts (original encodings)
+ the 1,450 LAMP-rewritten AI posts (frozen-instrument encodings from
features_encoded_rewritten.parquet). Same 1,740-doc composition as the
original test split, AI side attacked (symmetric self-rewrite design: each
model rewrote its own posts).

Detectors (all frozen artifacts, faithful protocol): structural
(narrative_strict, 187 feats), style-only (27), all-features (214) - XGB
refit deterministically on train+val with the committed hyperparameters
(artifacts/r6/variant_results_parity.json), seed 202616, the exact
construction of study_b/r6_s9_fixes.py. Nothing is retrained on rewritten
text.

HARD GATES (any mismatch = abort before durability numbers exist): each
frozen classifier must reproduce its recorded macro-F1 on the untouched
original test split - structural 0.9803 / style 0.8811 / all-features 0.9812
(band 0.9807-0.9813; canonical record: artifacts/METHODOLOGY.md section 6).

Also: per-AI-model breakdown, prediction-flip counts, 10k-resample bootstrap
CIs (domain-cluster primary, prompt secondary, seed 202616) on the attacked
structural macro-F1.

Inputs (gated; available to researchers on request - see MANIFEST.md):
  outputs/study_b/r6/features_encoded.parquet
  outputs/study_b/r7/features_encoded_rewritten.parquet
  outputs/study_b/r7/rewritten_{model}.jsonl (hashed only)
Public output to check against: artifacts/r7/durability_aggregates.json.

Run from the repository root:
  .venv/bin/python -m study_b.r7_durability_eval
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from study_b.r6_train import load, cols_for            # noqa: E402

R6 = Path("outputs/study_b/r6")
R7 = Path("outputs/study_b/r7")
RES6 = R6 / "results"
SEED = 202616
N_BOOT = 10_000
MODELS = ["claude", "deepseek", "gemini", "gpt", "kimi"]

# canonical original-test values (artifacts/METHODOLOGY.md section 6); the
# all-features band covers the recorded train-only (0.9807) vs faithful
# train+val (0.9812) protocol readings - faithful is expected.
EXPECT = {"structural": 0.9803, "style_only": 0.8811,
          "all_features": (0.9807, 0.9813), "all_features_point": 0.9812}


def sha16(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def fit_xgb(X, y, cfg):
    import xgboost as xgb
    return xgb.XGBClassifier(random_state=SEED, n_jobs=-1, tree_method="hist",
                             eval_metric="logloss", **cfg).fit(X, y)


def macro_f1(y, p):
    from sklearn.metrics import f1_score
    return float(f1_score(y, p, average="macro"))


def auprc(y, proba):
    from sklearn.metrics import average_precision_score
    return float(average_precision_score(y, proba))


def bootstrap_cis(y, pred, doc_ids, domains, rng):
    """10k-resample bootstrap CIs on macro-F1: prompt and domain-cluster."""
    out = {}
    for label, units_arr in (("prompt", doc_ids), ("domain_cluster", domains)):
        uniq = np.unique(units_arr)
        idx = {u: np.flatnonzero(units_arr == u) for u in uniq}
        stats = np.empty(N_BOOT)
        for b in range(N_BOOT):
            pick = rng.choice(uniq, size=len(uniq), replace=True)
            ii = np.concatenate([idx[u] for u in pick])
            stats[b] = macro_f1(y[ii], pred[ii])
        lo, hi = np.percentile(stats, [2.5, 97.5])
        out[label] = {"ci95": [round(float(lo), 4), round(float(hi), 4)],
                      "n_units": int(len(uniq))}
    return out


def eval_pack(y, pred, proba):
    return {"macro_f1": round(macro_f1(y, pred), 4),
            "auprc": round(auprc(y, proba), 4)}


def main() -> int:
    import pandas as pd
    R = {"seed": SEED, "n_boot": N_BOOT,
         "protocol": "faithful (finals refit on train+val with committed "
                     "hyperparameters; nothing retrained on rewritten text)",
         "attacked_composition": "290 original human test posts + 1,450 "
                                 "LAMP-rewritten AI test posts (5 models x "
                                 "290, symmetric self-rewrite)"}

    # ---------------- artifact hashes ---------------------------------------
    R["artifact_hashes_sha256_16"] = {
        "features_encoded.parquet": sha16(R6 / "features_encoded.parquet"),
        "features_encoded_rewritten.parquet":
            sha16(R7 / "features_encoded_rewritten.parquet"),
        **{f"rewritten_{m}.jsonl": sha16(R7 / f"rewritten_{m}.jsonl")
           for m in MODELS}}

    # ================= encoded-feature detectors ============================
    df, variants = load()
    parity = json.load(open(RES6 / "variant_results_parity.json"))
    trval = df[df.split.isin(["train", "val"])]
    te = df[df.split == "test"].reset_index(drop=True)
    assert len(te) == 1740 and (te.source == "human").sum() == 290

    rw = pd.read_parquet(R7 / "features_encoded_rewritten.parquet")
    assert list(rw.columns) == [c for c in df.columns if c != "split"], \
        "rewritten matrix layout != frozen layout"
    assert len(rw) == 1450 and rw.doc_id.nunique() == 290
    te_h = te[te.source == "human"]
    atk = pd.concat([te_h[rw.columns], rw], ignore_index=True)
    assert len(atk) == 1740 and atk.domain.notna().all()

    key = ["doc_id", "source"]
    feat_specs = [("structural", "narrative_strict"),
                  ("style_only", "style_only"),
                  ("all_features", "all_features")]
    R["parity_assertions"] = {}
    R["detectors"] = {}
    R["flip_counts"] = {}
    preds_atk = {}   # name -> attacked pred aligned to atk rows
    for name, variant in feat_specs:
        cols = cols_for(df, variants[variant])
        m = fit_xgb(trval[cols], trval.label_ai, parity[variant]["config"])
        pred_o = m.predict(te[cols])
        proba_o = m.predict_proba(te[cols])[:, 1]
        f1_o = round(macro_f1(te.label_ai, pred_o), 4)
        exp = EXPECT[name]
        if isinstance(exp, tuple):
            assert exp[0] <= f1_o <= exp[1], \
                f"PARITY FAIL {name}: {f1_o} outside {exp}"
        else:
            assert f1_o == exp, f"PARITY FAIL {name}: {f1_o} != {exp}"
        R["parity_assertions"][name] = {
            "n_features": len(variants[variant]), "config":
                parity[variant]["config"],
            "original_test_macro_f1": f1_o, "expected": exp, "status": "PASS"}
        print(f"parity {name}: {f1_o} PASS", flush=True)

        pred_a = m.predict(atk[cols])
        proba_a = m.predict_proba(atk[cols])[:, 1]
        R["detectors"][name] = {
            "original_test": eval_pack(te.label_ai, pred_o, proba_o),
            "attacked_test": eval_pack(atk.label_ai, pred_a, proba_a),
            "delta_macro_f1": round(
                macro_f1(atk.label_ai, pred_a) - macro_f1(te.label_ai, pred_o), 4)}
        preds_atk[name] = pred_a

        # flip counts: AI posts predicted AI originally -> human after attack
        o = te[te.source != "human"][key].assign(p=pred_o[
            (te.source != "human").to_numpy()])
        a = atk[atk.source != "human"][key].assign(p=pred_a[
            (atk.source != "human").to_numpy()])
        j = o.merge(a, on=key, suffixes=("_orig", "_atk"))
        assert len(j) == 1450
        R["flip_counts"][name] = {
            "ai_posts": 1450,
            "flipped_ai_to_human": int(((j.p_orig == 1) & (j.p_atk == 0)).sum()),
            "predicted_human_attacked": int((j.p_atk == 0).sum()),
            "predicted_human_original": int((j.p_orig == 0).sum())}

    # bootstrap CIs on attacked structural macro-F1
    rng = np.random.default_rng(SEED)
    pa = preds_atk["structural"]
    R["attacked_structural_bootstrap"] = bootstrap_cis(
        atk.label_ai.to_numpy(), pa, atk.doc_id.to_numpy(),
        atk.domain.to_numpy(), rng)
    R["attacked_structural_bootstrap"]["note"] = (
        "domain-cluster primary per prereg; 10k resamples seed 202616")
    print("bootstrap:", json.dumps(R["attacked_structural_bootstrap"]), flush=True)

    # ================= per-AI-model breakdown ===============================
    # structural macro-F1 on (290 humans + that model's 290 rewritten posts);
    # symmetric self-rewrite design.
    h_mask = (atk.source == "human").to_numpy()
    per_model = {}
    for mdl in MODELS:
        me = h_mask | (atk.source == mdl).to_numpy()
        per_model[mdl] = {
            "n": int(me.sum()),
            "structural_macro_f1": round(macro_f1(
                atk.label_ai.to_numpy()[me], preds_atk["structural"][me]), 4)}
    R["per_ai_model_attacked"] = per_model
    R["per_ai_model_note"] = ("humans (290, unchanged) + that model's 290 "
                              "self-rewritten posts; symmetric self-rewrite "
                              "design (each model rewrote its own posts)")

    json.dump(R, open(R7 / "durability_results.json", "w"), indent=2)
    print("written:", R7 / "durability_results.json", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
