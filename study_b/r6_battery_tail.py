#!/usr/bin/env python
"""R6 battery tail - the three robustness exhibits.

A. TEMPORAL CONTROL: era task (pre-2018 vs 2020+ human docs, domain-grouped
   5-fold) on the narrative-strict encoding; era-informative features; overlap
   with authorship SHAP; orthogonality ablation (drop top-N era features,
   re-run authorship on the committed splits).
B. ENTITY SCAN: v1's hard post-cutoff entity list over all 11,250 mirrors;
   per-model rates; headline sensitivity excluding flagged docs.
C. YC SENSITIVITY (item 18): headline test metrics + rarity means within
   YC-frame vs composite-frame subsets.

  .venv/bin/python -m study_b.r6_battery_tail
"""
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from study_b.r6_train import load, cols_for, fit  # noqa: E402

OUT = Path("outputs/study_b/r6/results")
SEED = 202616
PAT = re.compile(r"\b(ChatGPT|GPT-4o?|GPT-4\.\d|GPT-5(?:\.\d+)?|o1-preview|"
                 r"Google Gemini|Gemini (?:Pro|Ultra|Advanced|1\.5|2)|Claude [23](?:\.\d)?|"
                 r"Llama [23]|Mistral(?: AI| Large)|Midjourney v[5-9]|Sora|Grok|"
                 r"Microsoft Copilot|GitHub Copilot X)\b", re.I)


def main() -> int:
    import pandas as pd
    from sklearn.metrics import f1_score
    from sklearn.model_selection import GroupKFold

    df, variants = load()
    cols = cols_for(df, variants["narrative_strict"])
    results = json.load(open(OUT / "variant_results.json"))
    cfg = results["narrative_strict"]["config"]
    report = {}

    # ---------- A. temporal control -----------------------------------------
    h = pd.read_parquet("outputs/study_b/corpus/story_human_frozen.parquet")
    year = {r.doc_id: int(str(r.snapshot_ts)[:4]) for r in h.itertuples()}
    hu = df[df.source == "human"].copy()
    hu["year"] = hu.doc_id.map(year)
    era = hu[(hu.year <= 2017) | (hu.year >= 2020)].copy()
    era["y"] = (era.year >= 2020).astype(int)
    gkf = GroupKFold(n_splits=5)
    Xe = era[cols].to_numpy(dtype=np.float32)
    fes = []
    era_gain = np.zeros(len(cols))
    for tr, te in gkf.split(Xe, era.y, era.domain):
        m = fit(era.iloc[tr][cols], era.iloc[tr].y, cfg)
        fes.append(f1_score(era.iloc[te].y, m.predict(era.iloc[te][cols]),
                            average="macro"))
        era_gain += m.feature_importances_
    era_f1 = float(np.mean(fes))
    # authorship baseline + orthogonality ablation on committed splits
    tr_df = df[df.split == "train"]
    te_df = df[df.split == "test"]
    m_auth = fit(tr_df[cols], tr_df.label_ai, cfg)
    base = f1_score(te_df.label_ai, m_auth.predict(te_df[cols]), average="macro")
    order = np.argsort(-era_gain)
    ablation = {}
    for n in (25, 50, 100):
        keep = [c for i, c in enumerate(cols) if i not in set(order[:n])]
        m2 = fit(tr_df[keep], tr_df.label_ai, cfg)
        ablation[f"drop_top{n}_era_cols"] = round(
            float(f1_score(te_df.label_ai, m2.predict(te_df[keep]),
                           average="macro")), 4)
    top_era = {cols[i].split("__")[0] for i in order[:25]}
    import shap
    sv = shap.TreeExplainer(m_auth).shap_values(
        tr_df[cols].sample(800, random_state=SEED))
    auth_imp = np.abs(sv).mean(axis=0)
    top_auth = {cols[i].split("__")[0] for i in np.argsort(-auth_imp)[:25]}
    report["temporal"] = {
        "era_task_n": [int((era.y == 0).sum()), int((era.y == 1).sum())],
        "era_f1_grouped_cv": round(era_f1, 4),
        "authorship_test_f1_baseline": round(float(base), 4),
        "orthogonality_ablation": ablation,
        "top25_feature_overlap_era_vs_authorship": len(top_era & top_auth),
    }
    print("A temporal:", json.dumps(report["temporal"]))

    # ---------- B. entity scan ----------------------------------------------
    per, flagged = {}, {}
    for s_ in ("gpt", "claude", "gemini", "deepseek", "kimi"):
        n = tot = 0
        for l in open(f"outputs/study_b/mirrors/story_{s_}.jsonl"):
            r = json.loads(l)
            tot += 1
            if PAT.search(r["text"]):
                n += 1
                flagged.setdefault(r["doc_id"], set()).add(s_)
        per[s_] = {"flagged": n, "total": tot, "rate": round(n / tot, 4)}
    te_mask = df.split == "test"
    keep_mask = te_mask & ~df.apply(
        lambda r: r.source in flagged.get(r.doc_id, set()), axis=1)
    f1_all = f1_score(df[te_mask].label_ai, m_auth.predict(df[te_mask][cols]),
                      average="macro")
    f1_clean = f1_score(df[keep_mask].label_ai,
                        m_auth.predict(df[keep_mask][cols]), average="macro")
    report["entity_scan"] = {
        "per_model": per,
        "pooled_rate": round(sum(p["flagged"] for p in per.values())
                             / sum(p["total"] for p in per.values()), 4),
        "test_f1_all": round(float(f1_all), 4),
        "test_f1_excluding_flagged": round(float(f1_clean), 4),
        "test_rows_dropped": int(te_mask.sum() - keep_mask.sum()),
    }
    print("B entity:", json.dumps(report["entity_scan"]))

    # ---------- C. YC sensitivity (item 18) ---------------------------------
    is_yc = df.stratum.str.contains("yc", case=False, na=False)
    rar = pd.read_parquet(OUT / "rarity" / "rarity.parquet")
    rar = rar.merge(df[["doc_id", "source", "stratum"]].drop_duplicates(),
                    on=["doc_id", "source"], how="left")
    ryc = rar[rar.stratum.str.contains("yc", case=False, na=False)]
    rnon = rar[~rar.stratum.str.contains("yc", case=False, na=False)]
    def rgap(x):
        return round(float(x[x.source == "human"].rarity_trainval.mean()
                           - x[x.source != "human"].rarity_trainval.mean()), 4)
    sub = {}
    for label, mask in (("yc", te_mask & is_yc), ("non_yc", te_mask & ~is_yc)):
        part = df[mask]
        sub[label] = {
            "n_test_texts": int(mask.sum()),
            "test_macro_f1": round(float(f1_score(
                part.label_ai, m_auth.predict(part[cols]), average="macro")), 4),
        }
    sub["rarity_gap_yc"] = rgap(ryc)
    sub["rarity_gap_non_yc"] = rgap(rnon)
    report["yc_sensitivity"] = sub
    print("C yc:", json.dumps(sub))

    json.dump(report, open(OUT / "battery_tail.json", "w"), indent=2)
    print("battery tail written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
