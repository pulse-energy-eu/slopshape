#!/usr/bin/env python
"""C1: raw-text baselines on the FROZEN splits (original's Table 2 anchors).

Implemented here: length-only logistic; stylometric feature set + XGB;
TF-IDF (word 1-2 grams) + XGB. (Binoculars and ModernBERT follow separately -
heavier runtimes; tracked in the open-items list.)

All models use the committed splits (seed 202616, domain-disjoint, discovery
pool excluded) and report test macro-F1 + AUPRC + accuracy.

  .venv/bin/python -m study_b.r6_baselines
"""
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

OUT = Path("outputs/study_b/r6/results")
SEED = 202616


def load_texts():
    import pandas as pd
    h = pd.read_parquet("outputs/study_b/corpus/story_human_frozen.parquet")
    pool = set(json.loads(Path("outputs/study_b/r3/discovery_pool.json").read_text())["doc_ids"])
    rows = [{"doc_id": r.doc_id, "source": "human", "text": r.story_human}
            for r in h.itertuples() if r.doc_id not in pool]
    for f in sorted(Path("outputs/study_b/mirrors").glob("story_*.jsonl")):
        for line in open(f):
            r = json.loads(line)
            if r["doc_id"] not in pool:
                rows.append({"doc_id": r["doc_id"], "source": r["source"],
                             "text": r["text"]})
    df = pd.DataFrame(rows)
    splits = json.load(open("outputs/study_b/r6/splits.json"))["doc_split"]
    df["split"] = df.doc_id.map(splits)
    df["y"] = (df.source != "human").astype(int)
    return df


FUNCTION_WORDS = ("the of and a to in is that it for on with as are was be this "
                  "by an at or from but not have has had they you we he she i "
                  "their its our your my his her them us him me who which what "
                  "when where how why can could would should will may might must "
                  "do does did done being been if then than so because while "
                  "although though however therefore moreover also just only "
                  "very more most much many some any all both each few no nor "
                  "yet after before during between among through over under "
                  "about into onto upon again once here there now such own same "
                  "other another these those").split()[:100]
assert len(FUNCTION_WORDS) == 100


def _syllables(word: str) -> int:
    w = word.lower().strip(".,;:!?\"'()")
    if not w:
        return 0
    count, prev_v = 0, False
    for ch in w:
        v = ch in "aeiouy"
        if v and not prev_v:
            count += 1
        prev_v = v
    return max(1, count)


def stylometrics(texts):
    """144 hand-crafted dims per the original's spec: length stats, vocabulary
    richness, 100 function words, punctuation, dialogue features, readability."""
    feats = []
    for t in texts:
        words = t.split()
        n_w = max(1, len(words))
        n_c = max(1, len(t))
        sents = [x for x in re.split(r"[.!?]+\s", t) if x.strip()]
        n_s = max(1, len(sents))
        sl = [len(x.split()) for x in sents]
        wl = [len(w) for w in words]
        lower = t.lower()
        toks = [w.lower().strip(".,;:!?\"'()") for w in words]
        vocab = {}
        for w in toks:
            vocab[w] = vocab.get(w, 0) + 1
        syls = [_syllables(w) for w in words]
        total_syl = max(1, sum(syls))
        # length stats (12)
        length = [n_w, n_c, n_s, np.mean(wl), np.std(wl), max(wl),
                  np.mean(sl), np.std(sl), max(sl) if sl else 0,
                  min(sl) if sl else 0, t.count("\n\n") + 1,
                  n_w / (t.count("\n\n") + 1)]
        # vocabulary richness (8)
        hapax = sum(1 for c in vocab.values() if c == 1)
        dis = sum(1 for c in vocab.values() if c == 2)
        m2 = sum(c * c for c in vocab.values())
        yule_k = 1e4 * (m2 - n_w) / (n_w * n_w)
        vocab_f = [len(vocab) / n_w, hapax / n_w, dis / n_w, yule_k,
                   len(vocab) / max(1, np.sqrt(n_w)),
                   np.mean([len(w) for w in vocab]) if vocab else 0,
                   sum(1 for w in toks if len(w) >= 7) / n_w,
                   sum(1 for w in toks if len(w) <= 3) / n_w]
        # function words (100)
        fw = [lower.count(f" {w} ") / n_w for w in FUNCTION_WORDS]
        # punctuation (12)
        punct = [t.count(c) / n_w for c in (",", ";", ":", "?", "!", "-",
                                             "(", ")", "\"", "'", "%", "$")]
        # dialogue features (6)
        quotes = re.findall(r'"([^"]{2,400})"', t)
        dlg_words = sum(len(q.split()) for q in quotes)
        dialogue = [len(quotes), len(quotes) / n_s, dlg_words / n_w,
                    np.mean([len(q.split()) for q in quotes]) if quotes else 0,
                    lower.count(" said ") / n_s,
                    sum(1 for q in quotes if q.strip().endswith("?")) / max(1, len(quotes))]
        # readability (6)
        asl = n_w / n_s
        aspw = total_syl / n_w
        flesch = 206.835 - 1.015 * asl - 84.6 * aspw
        fk_grade = 0.39 * asl + 11.8 * aspw - 15.59
        fog = 0.4 * (asl + 100 * sum(1 for x in syls if x >= 3) / n_w)
        ari = 4.71 * (n_c / n_w) + 0.5 * asl - 21.43
        readab = [flesch, fk_grade, fog, ari, aspw,
                  sum(1 for x in syls if x >= 3) / n_w]
        feats.append(length + vocab_f + fw + punct + dialogue + readab)
    arr = np.array(feats, dtype=np.float32)
    assert arr.shape[1] == 144, arr.shape
    return arr


def evaluate(name, model, Xtr, ytr, Xte, yte, results):
    from sklearn.metrics import f1_score, average_precision_score, accuracy_score
    model.fit(Xtr, ytr)
    proba = model.predict_proba(Xte)[:, 1]
    pred = (proba >= 0.5).astype(int)
    results[name] = {
        "test_macro_f1": round(float(f1_score(yte, pred, average="macro")), 4),
        "test_auprc": round(float(average_precision_score(yte, proba)), 4),
        "test_acc": round(float(accuracy_score(yte, pred)), 4)}
    print(name, results[name], flush=True)


def main() -> int:
    import xgboost as xgb
    from sklearn.linear_model import LogisticRegression
    from sklearn.feature_extraction.text import TfidfVectorizer

    df = load_texts()
    tr = df[df.split == "train"]
    te = df[df.split == "test"]
    print(f"texts: train {len(tr)} test {len(te)}", flush=True)
    results = {}

    # 1. length-only logistic
    evaluate("length_only_logistic",
             LogisticRegression(max_iter=1000),
             np.log1p(tr.text.str.split().str.len()).to_numpy().reshape(-1, 1),
             tr.y,
             np.log1p(te.text.str.split().str.len()).to_numpy().reshape(-1, 1),
             te.y, results)

    # 2. stylometric + XGB
    evaluate("stylometric_xgb",
             xgb.XGBClassifier(n_estimators=420, max_depth=8, learning_rate=0.1,
                               random_state=SEED, n_jobs=-1, tree_method="hist",
                               eval_metric="logloss"),
             stylometrics(tr.text.tolist()), tr.y,
             stylometrics(te.text.tolist()), te.y, results)

    # 3. TF-IDF + XGB
    vec = TfidfVectorizer(ngram_range=(1, 2), max_features=50000,
                          sublinear_tf=True, min_df=3)
    Xtr = vec.fit_transform(tr.text)
    Xte = vec.transform(te.text)
    evaluate("tfidf_xgb",
             xgb.XGBClassifier(n_estimators=420, max_depth=8, learning_rate=0.1,
                               random_state=SEED, n_jobs=-1, tree_method="hist",
                               eval_metric="logloss"),
             Xtr, tr.y, Xte, te.y, results)

    results["_note"] = ("binoculars and ModernBERT pending (heavier runtimes); "
                        "narrative-strict headline for comparison: 0.9725 macro-F1")
    json.dump(results, open(OUT / "baselines.json", "w"), indent=2)
    print("baselines written", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
