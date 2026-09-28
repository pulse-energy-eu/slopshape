#!/usr/bin/env python
"""R8 format-sensitivity probe: which features answer differently when only
the input format changes?

Human posts are scored as extracted and normalized, and the extracted text
keeps the page title only for some posts. Generated posts are scored as
produced: they open with a title line and most carry markdown. The probe
rescores samples with only the format changed, using the frozen stage-5
scorer (study_b.r5_apply: PROMPT, model, Applier) and the frozen r6 encoder
layout.

Arms:
  A1  AI posts through normalize(): markdown stripped, title kept as a plain
      first line (isolates the markdown effect)
  A2  as A1, title line removed (isolates the title effect on top of A1)
  H1  human posts whose scored text has no title: stored title prepended as a
      plain first line (the reverse direction)

Splits:
  test      the confirmation probe (outputs/study_b/r8_title_probe/), 50 AI
            posts per model and every eligible human test post
  trainval  the selection probe (outputs/study_b/r8_trainval_probe/), train+val
            docs only: 50 AI posts per model and 250 eligible human posts.
            Its screen defines the format-sensitivity exclusion set
            (artifacts/FILED_DECISIONS.md, filed before any trainval call)

Screen rule (screen command): for each of the 214 surviving features and
each arm, TVD between the feature's answer distribution on the original
scoring and on the arm, over the arm's fully scored posts. noise95 is the
95th percentile of the same TVD between the full run and a repeat run, over
40 draws of 250 full-vs-repeat answer pairs (train+val docs only). A feature
is format-sensitive if its TVD exceeds 2 x noise95 + 0.05 in any arm.

  python -m study_b.r8_title_probe build  --split trainval
  python -m study_b.r8_title_probe score  --split trainval  # $60 cap
  python -m study_b.r8_title_probe screen --split trainval
  python -m study_b.r8_title_probe screen --split test \
      --out outputs/study_b/r8_trainval_probe/test_confirmation.json
  python -m study_b.r8_title_probe eval   --split test
"""
import argparse
import concurrent.futures as cf
import json
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from study_b.normalize import normalize  # noqa: E402

OUTS = {"test": Path("outputs/study_b/r8_title_probe"),
        "trainval": Path("outputs/study_b/r8_trainval_probe")}
SPLITS = {"test": {"test"}, "trainval": {"train", "val"}}
R6 = Path("outputs/study_b/r6")
R5 = Path("outputs/study_b/r5")
SEED = 202616
N_AI_PER_MODEL = 50
N_HUMAN_TRAINVAL = 250
MODELS = ["gpt", "claude", "gemini", "deepseek", "kimi"]
ARMS = ["A1", "A2", "H1"]
# screen rule constants (filed in artifacts/FILED_DECISIONS.md)
NOISE_SEED, NOISE_DRAWS, NOISE_PAIRS = 0, 40, 250
FLAG_MULT, FLAG_ADD = 2.0, 0.05
FULL_SCORE_SHARE = 0.95
PIN, POUT = 0.75, 3.75  # $/M, as study_b.r5_apply


def first_line(t: str) -> str:
    return t.strip().split("\n")[0].strip()


def clean_title(t: str) -> str:
    return str(t).split(" | ")[0].strip()


def human_has_title(text: str, title: str) -> bool:
    """The scored text already carries its title: its first line equals the
    cleaned stored title, or one is a 40-character prefix of the other
    (extraction can truncate either side). H1 draws only from posts where
    this is False."""
    fl, ti = first_line(text).lower(), clean_title(title).lower()
    if not ti:
        return False
    return fl == ti or fl.startswith(ti[:40]) or ti.startswith(fl[:40])


def build(split: str) -> int:
    import pandas as pd
    out = OUTS[split]
    if any((out / f"texts_{a}.jsonl").exists() for a in ARMS):
        print(f"{out}: arm texts exist, not overwriting", file=sys.stderr)
        return 1
    splits = json.load(open(R6 / "splits.json"))["doc_split"]
    keep = SPLITS[split]
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)

    ai = defaultdict(list)
    for m in MODELS:
        for line in open(f"outputs/study_b/mirrors/story_{m}.jsonl"):
            r = json.loads(line)
            if splits.get(r["doc_id"]) in keep:
                ai[m].append(r)
    a1, a2 = [], []
    for m in MODELS:
        pick = rng.sample(sorted(ai[m], key=lambda r: r["doc_id"]),
                          N_AI_PER_MODEL)
        for r in pick:
            norm = normalize(r["text"])
            lines = norm.strip().split("\n")
            title, body = lines[0].strip(), "\n".join(lines[1:]).strip()
            assert len(title.split()) <= 30, (r["doc_id"], m, title[:80])
            a1.append({"doc_id": r["doc_id"], "source": m, "text": norm})
            a2.append({"doc_id": r["doc_id"], "source": m, "text": body,
                       "removed_title": title})

    h = pd.read_parquet("outputs/study_b/corpus/story_human_frozen.parquet")
    h1 = []
    for r in sorted(h.itertuples(), key=lambda r: r.doc_id):
        if splits.get(r.doc_id) not in keep:
            continue
        ti = clean_title(r.title)
        if human_has_title(r.story_human, r.title) or len(ti.split()) < 3:
            continue
        h1.append({"doc_id": r.doc_id, "source": "human",
                   "text": f"{ti}\n{r.story_human}", "added_title": ti})
    if split == "trainval":
        print(f"H1 pool: {len(h1)} eligible human posts", file=sys.stderr)
        h1 = rng.sample(h1, N_HUMAN_TRAINVAL)

    for name, rows in (("A1", a1), ("A2", a2), ("H1", h1)):
        with open(out / f"texts_{name}.jsonl", "w") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        print(f"{name}: {len(rows)} texts", file=sys.stderr)
    return 0


def spent_so_far(out: Path) -> float:
    """Spend over every stored call of this split's arms (resume-safe cap)."""
    usd = 0.0
    for arm in ARMS:
        p = out / f"answers_{arm}.jsonl"
        if not p.exists():
            continue
        for line in open(p):
            try:
                u = json.loads(line).get("usage") or {}
            except json.JSONDecodeError:
                continue
            usd += (u.get("in", 0) * PIN + u.get("out", 0) * POUT) / 1e6
    return usd


def score(split: str, max_usd: float, concurrency: int,
          limit: int | None) -> int:
    from study_b.r5_apply import Applier, load_features
    out = OUTS[split]
    by_dim = load_features()
    app = Applier()
    base = spent_so_far(out)
    print(f"{split}: ${base:.2f} already spent, cap ${max_usd}", file=sys.stderr)
    for arm in ARMS:
        texts = [json.loads(l) for l in open(out / f"texts_{arm}.jsonl")]
        if limit:
            texts = texts[:limit]
        outfile = out / f"answers_{arm}.jsonl"
        done = set()
        if outfile.exists():
            for l in open(outfile):
                r = json.loads(l)
                if "answers" in r:
                    done.add((r["doc_id"], r["source"], r["dim"]))
        todo = [(t, d, f) for t in texts for d, f in sorted(by_dim.items())
                if (t["doc_id"], t["source"], d) not in done]
        print(f"{arm}: {len(todo)} calls to run ({len(done)} done)",
              file=sys.stderr)
        t0, n_ok, n_err = time.time(), 0, 0
        with open(outfile, "a") as fh, cf.ThreadPoolExecutor(concurrency) as ex:
            for i, rec in enumerate(ex.map(
                    lambda u: app.call(u[0], u[1], u[2], f"r8_{split}_{arm}"),
                    todo), 1):
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                n_ok += "answers" in rec
                n_err += "error" in rec
                if i % 250 == 0:
                    print(f"  {arm} [{i}/{len(todo)}] ok={n_ok} err={n_err} "
                          f"spent=${base + app.spent:.2f} "
                          f"{i / max(1, time.time() - t0) * 3600:.0f}/h",
                          file=sys.stderr)
                if base + app.spent > max_usd:
                    print(f"STOPPED: spend cap ${max_usd}", file=sys.stderr)
                    return 1
        print(f"{arm} done: {n_ok} ok, {n_err} failed, total spend "
              f"${base + app.spent:.2f}", file=sys.stderr)
    return 0


def load_answers(path: Path) -> dict:
    from study_b.r5_qa import canon
    ans = defaultdict(dict)
    for l in open(path):
        try:
            r = json.loads(l)
        except json.JSONDecodeError:  # partial last line while scoring runs
            continue
        if "answers" in r:
            for fid, v in r["answers"].items():
                ans[(r["doc_id"], r["source"])][fid] = canon(v)
    return ans


def tvd(pairs: list, f: str) -> float:
    """Total variation distance between the answer distributions of f on
    the left and right members of (left_answers, right_answers) pairs."""
    ca = Counter(a.get(f) for a, _ in pairs)
    cb = Counter(b.get(f) for _, b in pairs)
    return 0.5 * sum(abs(ca[v] - cb[v]) for v in set(ca) | set(cb)) / len(pairs)


def noise95(fids: list, orig: dict) -> dict:
    """Per feature: 95th-percentile TVD over NOISE_DRAWS draws of NOISE_PAIRS
    full-vs-repeat answer pairs, train+val docs only."""
    splits = json.load(open(R6 / "splits.json"))["doc_split"]
    pairs = []
    for k in range(1, 6):
        rep = load_answers(R5 / f"answers_repeat_{k}.jsonl")
        for key in sorted(rep):
            if key in orig and splits.get(key[0]) in SPLITS["trainval"]:
                pairs.append((orig[key], rep[key]))
    rng = random.Random(NOISE_SEED)
    draws = [rng.sample(pairs, min(NOISE_PAIRS, len(pairs)))
             for _ in range(NOISE_DRAWS)]
    idx = int(0.95 * NOISE_DRAWS) - 1
    return {"n_pairs_pool": len(pairs),
            "noise95": {f: sorted(tvd(d, f) for d in draws)[idx] for f in fids}}


def fully_scored(new: dict, orig: dict) -> list:
    return sorted(k for k in new if k in orig
                  and len(new[k]) >= FULL_SCORE_SHARE * len(orig[k]))


def screen(split: str, out_path: Path | None) -> int:
    from study_b.r6_build import surviving_features
    out = OUTS[split]
    feats = surviving_features()
    fids = [f["id"] for f in feats]
    style = {f["id"] for f in feats if f["is_style"]}
    orig = load_answers(R5 / "answers_full.jsonl")
    nz = noise95(fids, orig)
    arms = {}
    for arm in ARMS:
        new = load_answers(out / f"answers_{arm}.jsonl")
        keys = fully_scored(new, orig)
        arms[arm] = {"n": len(keys),
                     "pairs": [(orig[k], new[k]) for k in keys]}
    rows = []
    for f in fids:
        thr = FLAG_MULT * nz["noise95"][f] + FLAG_ADD
        t = {a: round(tvd(arms[a]["pairs"], f), 4) for a in ARMS}
        rows.append({"feature": f, "style": f in style,
                     "noise95": round(nz["noise95"][f], 4),
                     "threshold": round(thr, 4), "tvd": t,
                     "flag_arms": [a for a in ARMS if t[a] > thr],
                     "flagged": any(t[a] > thr for a in ARMS)})
    rows.sort(key=lambda r: -max(r["tvd"][a] - r["threshold"] for a in ARMS))
    flagged = [r["feature"] for r in rows if r["flagged"]]
    res = {"split": split,
           "rule": {"statistic": "TVD of per-feature answer distributions, "
                                 "original scoring vs arm, fully scored posts",
                    "noise": f"95th percentile over {NOISE_DRAWS} draws of "
                             f"{NOISE_PAIRS} full-vs-repeat pairs (train+val "
                             f"docs), random.Random({NOISE_SEED})",
                    "flag": f"TVD > {FLAG_MULT} x noise95 + {FLAG_ADD} in any "
                            f"of {ARMS}",
                    "full_score_share": FULL_SCORE_SHARE},
           "n_features_screened": len(fids),
           "noise_pairs_pool": nz["n_pairs_pool"],
           "n_per_arm": {a: arms[a]["n"] for a in ARMS},
           "flagged": flagged, "n_flagged": len(flagged),
           "features": rows}
    dest = out_path or out / "screen.json"
    if dest.exists():
        print(f"{dest} exists, not overwriting", file=sys.stderr)
        return 1
    json.dump(res, open(dest, "w"), indent=1)
    print(f"{split}: {len(flagged)} of {len(fids)} flagged: {flagged}",
          file=sys.stderr)
    for r in rows[:max(len(flagged) + 6, 12)]:
        print(f"  {r['feature']:13s} noise95 {r['noise95']:.3f} thr "
              f"{r['threshold']:.3f}  A1 {r['tvd']['A1']:.3f}  A2 "
              f"{r['tvd']['A2']:.3f}  H1 {r['tvd']['H1']:.3f}"
              f"{'  <== ' + ','.join(r['flag_arms']) if r['flagged'] else ''}",
              file=sys.stderr)
    return 0


def encode(answers: dict):
    """Frozen r6 layout, identical construction to r7_encode_rewritten."""
    import numpy as np
    import pandas as pd
    from study_b.r5_qa import canon
    from study_b.r6_build import surviving_features
    cols = {}
    for f in surviving_features():
        vals = [canon(v) for v in f.get("values", [])]
        if f.get("type") == "multi_select":
            for v in vals:
                cols[f"{f['id']}__{v}"] = ("multi", f["id"], v)
        elif f.get("type") in ("ordinal", "scale"):
            cols[f"{f['id']}__ord"] = ("ord", f["id"], vals)
        else:
            for v in vals:
                cols[f"{f['id']}__{v}"] = ("onehot", f["id"], v)
    names = sorted(cols)
    rows, keys = [], []
    for key, fa in sorted(answers.items()):
        row = np.full(len(names), np.nan, dtype=np.float32)
        for j, cn in enumerate(names):
            kind, fid, spec = cols[cn]
            a = fa.get(fid)
            if a is None:
                continue
            if kind == "onehot":
                row[j] = 1.0 if a == spec else 0.0
            elif kind == "multi":
                row[j] = 1.0 if spec in (set(a.split("|")) if a else set()) else 0.0
            else:
                row[j] = float(spec.index(a)) if a in spec else np.nan
        rows.append(row)
        keys.append(key)
    X = pd.DataFrame(np.vstack(rows), columns=names)
    X.index = pd.MultiIndex.from_tuples(keys, names=["doc_id", "source"])
    return X


def evaluate(split: str, report: Path) -> int:
    """Per-arm answer shifts and the structural classifier's verdicts on the
    original and the reformatted texts. The classifier is the final
    structural model (variant sets and val-selected configuration from the
    r6 results), refit on train+val; on the trainval split every verdict is
    in-sample."""
    import numpy as np
    import pandas as pd
    import xgboost as xgb
    from sklearn.metrics import f1_score

    if report.exists():
        print(f"{report} exists, not overwriting", file=sys.stderr)
        return 1
    out = OUTS[split]
    frozen = pd.read_parquet(R6 / "features_encoded.parquet")
    frozen["split"] = frozen.doc_id.map(
        json.load(open(R6 / "splits.json"))["doc_split"])
    struct = json.load(open(R6 / "variant_sets.json"))["narrative_strict"]
    par = json.load(open(R6 / "results" / "variant_results_parity.json"))[
        "narrative_strict"]
    core = json.load(open(R6 / "results" / "core_values_selection.json"))[
        "core_features"]
    pref = tuple(f"{f}__" for f in struct)
    cols = [c for c in frozen.columns if c.startswith(pref)]
    tv = frozen[frozen.split.isin(["train", "val"])]
    te = frozen[frozen.split == "test"]
    model = xgb.XGBClassifier(random_state=SEED, n_jobs=-1, tree_method="hist",
                              eval_metric="logloss", **par["config"])
    model.fit(tv[cols], tv.label_ai)
    f1 = f1_score(te.label_ai, model.predict(te[cols]), average="macro")
    assert round(f1, 4) == par["test"]["macro_f1"], f"refit drifted: {f1:.4f}"

    orig_ans = load_answers(R5 / "answers_full.jsonl")
    fz = frozen.set_index(["doc_id", "source"])

    # noise baseline: full run vs each repeat run, same docs, per feature
    noise = Counter()
    noise_n = Counter()
    for k in range(1, 6):
        rep = load_answers(R5 / f"answers_repeat_{k}.jsonl")
        for key, fa in rep.items():
            for fid in core:
                if fid in fa and fid in orig_ans.get(key, {}):
                    noise_n[fid] += 1
                    noise[fid] += fa[fid] != orig_ans[key][fid]

    res_all = {"split": split, "in_sample": split == "trainval",
               "structural_config": par["config"],
               "noise_flip_rate": {f: round(noise[f] / noise_n[f], 3)
                                   for f in core if noise_n[f]}}
    for arm in ARMS:
        new = load_answers(out / f"answers_{arm}.jsonl")
        keys = [k for k in new if k in orig_ans and k in fz.index
                and len(new[k]) >= FULL_SCORE_SHARE * len(orig_ans[k])]
        if not keys:
            continue
        Xn = encode({k: new[k] for k in keys})
        Xo = fz.loc[keys, [c for c in frozen.columns if "__" in c]]
        res = {"n": len(keys)}
        res["flip_rate"] = {
            f: round(float(np.mean([new[k].get(f) != orig_ans[k].get(f)
                                    for k in keys])), 3) for f in core}
        res["title_value_rate"] = {
            "PUR_OUT_003=title": {
                "orig": round(float(np.mean([orig_ans[k].get("PUR_OUT_003") == "title" for k in keys])), 3),
                "arm": round(float(np.mean([new[k].get("PUR_OUT_003") == "title" for k in keys])), 3)},
            "AUD_PRB_002=1_title_or_subtitle": {
                "orig": round(float(np.mean([orig_ans[k].get("AUD_PRB_002") == "1_title_or_subtitle" for k in keys])), 3),
                "arm": round(float(np.mean([new[k].get("AUD_PRB_002") == "1_title_or_subtitle" for k in keys])), 3)},
        }
        po = model.predict_proba(Xo[cols])[:, 1]
        pn = model.predict_proba(Xn[cols])[:, 1]
        res["structural"] = {
            "called_ai_orig": int((po >= .5).sum()),
            "called_ai_arm": int((pn >= .5).sum()),
            "share_called_ai_orig": round(float((po >= .5).mean()), 3),
            "share_called_ai_arm": round(float((pn >= .5).mean()), 3),
            "mean_p_ai_orig": round(float(po.mean()), 3),
            "mean_p_ai_arm": round(float(pn.mean()), 3),
            "verdict_flips": int(((po >= .5) != (pn >= .5)).sum()),
        }
        if arm != "H1":
            res["by_model_called_ai_arm"] = {
                s: round(float((model.predict_proba(
                    Xn.loc[[k for k in keys if k[1] == s], cols])[:, 1] >= .5).mean()), 3)
                for s in MODELS if any(k[1] == s for k in keys)}
        res_all[arm] = res
    json.dump(res_all, open(report, "w"), indent=1)
    print(json.dumps(res_all, indent=1))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "score", "screen", "eval"])
    ap.add_argument("--split", choices=sorted(OUTS), default="test")
    ap.add_argument("--max-usd", type=float, default=60.0)
    ap.add_argument("--concurrency", type=int, default=16)
    ap.add_argument("--limit", type=int, default=None,
                    help="pilot: first N texts per arm")
    ap.add_argument("--out", type=Path, default=None,
                    help="screen/eval output file (never overwritten)")
    a = ap.parse_args()
    if a.cmd == "build":
        return build(a.split)
    if a.cmd == "score":
        return score(a.split, a.max_usd, a.concurrency, a.limit)
    if a.cmd == "screen":
        return screen(a.split, a.out)
    return evaluate(a.split, a.out or OUTS[a.split] / "report.json")


if __name__ == "__main__":
    sys.exit(main())
