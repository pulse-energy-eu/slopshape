#!/usr/bin/env python
"""Temporal control: is the human-vs-AI signal really an old-vs-new signal?

Every human document predates 2022-11-30 by construction (that is how we
guarantee no human doc was secretly AI-assisted). So "human" and "written before
2023" are the same set, and a critic can argue the classifier learned publication
era rather than authorship. Blog conventions genuinely changed 2016 -> 2022.

The test throws the AI out entirely and asks the identical pipeline, same 290
features, to separate OLD human writing from RECENT human writing:

    pre-2017 human    vs    2020+ human

PRE-COMMITTED THRESHOLDS (fixed before the data existed):
    < 65  -> era effect is small. The human-vs-AI result is about authorship.
             Proceed.
    65-80 -> material era effect. Must be reported and controlled (restrict the
             human corpus to a narrow window, or report era-adjusted numbers).
    > 80  -> era is as strong as authorship. The headline claim is compromised.

Grouping is by DOMAIN, not prompt: a domain's posts cluster in time, so a
prompt-grouped split would let the model learn the domain and score era for free.

The most informative diagnostic is not the number but the FEATURE OVERLAP: if
the features that separate old-from-new human writing are disjoint from those
that separate human-from-AI, the confound is benign even at a moderate score.
If they are the same features, the result is compromised even at a low one.

  .venv/bin/python study_b/temporal_control.py
"""
import glob
import json
import pathlib
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vendor/storyscope"))

from sklearn.metrics import f1_score  # noqa: E402
from sklearn.model_selection import GroupKFold  # noqa: E402
import xgboost as xgb  # noqa: E402

from storyscope.utils.feature_encoder import (  # noqa: E402
    build_feature_type_map, encode_features, get_taxonomy_feature_ids, load_taxonomy)

PIPE = ROOT / "outputs/study_b/pipeline"
TAX = PIPE / "taxonomy/clustered_0.70/condensed_taxonomy_0.7.json"
OLD_MAX, NEW_MIN = 2017, 2020
XGB = dict(n_estimators=420, max_depth=8, reg_lambda=2.0,
           eval_metric="logloss", n_jobs=-1, random_state=0)


def fid_of(col):
    return col.split("__")[0]


def feature_names():
    raw = json.load(open(TAX))["feature_taxonomy"]
    out = {}
    for dim, dbody in raw.items():
        for asp, abody in (dbody.get("aspects") or {}).items():
            feats = abody.get("features") or abody
            items = feats.items() if isinstance(feats, dict) else [(f.get("id"), f) for f in feats]
            for fid, f in items:
                if isinstance(f, dict):
                    out[fid] = f"[{dim}] {f.get('name', '')}"
    return out


def load_all():
    rows = []
    for f in glob.glob(str(PIPE / "features/*/*.features.json")):
        d = json.load(open(f))
        rows.append({"story_title": d.get("title") or d.get("story_title"),
                     "author": pathlib.Path(f).parent.name, **(d.get("features") or {})})
    df = pd.DataFrame(rows)
    w = pd.read_parquet(PIPE / "corpus_wide.parquet")[["title", "doc_id"]]
    hum = pd.read_parquet(ROOT / "outputs/study_b/corpus/story_human_frozen.parquet")
    hum = hum.assign(yr=pd.to_datetime(hum.snapshot_ts, errors="coerce", utc=True).dt.year)
    meta = w.merge(hum[["doc_id", "domain", "stratum", "yr"]], on="doc_id", how="left")
    return df.merge(meta, left_on="story_title", right_on="title", how="left")


def encode(sub, fids, ftypes):
    sub = sub.copy()
    for c in fids:
        if c not in sub.columns:
            sub[c] = None
    X, cols = encode_features(sub, fids, ftypes, mode="multi_hot")
    return np.asarray(X, np.float32), np.array(cols)


def cv_importance(X, y, groups, label):
    """Domain-grouped CV; returns (mean F1, importances from fold 0)."""
    scores = []
    for tr, te in GroupKFold(n_splits=5).split(X, y, groups):
        if len(set(y[te])) < 2:
            continue
        m = xgb.XGBClassifier(**XGB).fit(X[tr], y[tr])
        scores.append(f1_score(y[te], m.predict(X[te]), average="macro") * 100)
    tr, te = next(GroupKFold(n_splits=5).split(X, y, groups))
    imp = xgb.XGBClassifier(**XGB).fit(X[tr], y[tr]).feature_importances_
    print(f"  {label:44} {np.mean(scores):5.1f} +/- {np.std(scores):4.1f}")
    return np.mean(scores), imp


def main():
    df = load_all()
    tax = load_taxonomy(str(TAX))
    ftypes, fids = build_feature_type_map(tax), get_taxonomy_feature_ids(tax)
    names = feature_names()

    hum = df[df.author == "human"]
    old = hum[hum.yr <= OLD_MAX]
    new = hum[hum.yr >= NEW_MIN]
    print(f"human docs featurized: {len(hum)}")
    print(f"  pre-{OLD_MAX+1}: {len(old)} docs / {old.domain.nunique()} domains")
    print(f"  {NEW_MIN}+    : {len(new)} docs / {new.domain.nunique()} domains\n")
    if len(old) < 50 or len(new) < 50:
        sys.exit("not enough docs in one era yet - is the temporal phase still running?")

    print("=== TEST 1: OLD vs RECENT human writing (domain-grouped) ===")
    era = pd.concat([old, new]).reset_index(drop=True)
    Xe, cols = encode(era, fids, ftypes)
    ye = (era.yr <= OLD_MAX).astype(int).values
    f1_era, imp_era = cv_importance(Xe, ye, era.domain.fillna("NA").values,
                                    f"pre-{OLD_MAX+1} vs {NEW_MIN}+ human")

    print("\n=== TEST 2: reference - human vs AI on the same features ===")
    comp = df.groupby("story_title").author.nunique()
    par = df[df.story_title.isin(comp[comp == 6].index)].reset_index(drop=True)
    Xh, _ = encode(par, fids, ftypes)
    yh = (par.author == "human").astype(int).values
    f1_auth, imp_auth = cv_importance(Xh, yh, par.domain.fillna("NA").values, "human vs AI")

    print("\n=== TEST 3: feature overlap (the diagnostic that matters) ===")
    top_era = {fid_of(c) for c in pd.Series(imp_era, index=cols).nlargest(25).index}
    top_auth = {fid_of(c) for c in pd.Series(imp_auth, index=cols).nlargest(25).index}
    shared = top_era & top_auth
    print(f"  top-25 era features       : {len(top_era)}")
    print(f"  top-25 authorship features: {len(top_auth)}")
    print(f"  SHARED                    : {len(shared)}  "
          f"({len(shared)/max(1,len(top_era))*100:.0f}% of era features)")
    if shared:
        print("  shared features (these would be the compromising ones):")
        for f in sorted(shared):
            print(f"    - {names.get(f, f)}")
    print("\n  era-only top features (benign - era markers we can name):")
    for f in sorted(top_era - top_auth)[:8]:
        print(f"    - {names.get(f, f)}")

    print("\n" + "=" * 62)
    verdict = ("PASS - era effect small; result is about authorship" if f1_era < 65 else
               "QUALIFIED - material era effect, must be reported/controlled"
               if f1_era <= 80 else
               "FAIL - era is as strong as authorship; headline compromised")
    print(f"  era F1 {f1_era:.1f} vs authorship F1 {f1_auth:.1f}")
    print(f"  VERDICT: {verdict}")
    print("=" * 62)


if __name__ == "__main__":
    main()
