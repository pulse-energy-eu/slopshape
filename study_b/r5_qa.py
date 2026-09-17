#!/usr/bin/env python
"""R5 QA utilities: subset selection, coverage check, repeatability alpha,
cost projection.

  select    seeded subsets: cov_docs.json (2 doc_ids -> 12 texts),
            repeat_docs.json (10 doc_ids -> 60 texts, 10 per source)
  coverage  aspect-vs-single coverage % + cross-mode agreement (report)
  alpha     Krippendorff nominal alpha across repeat_1..5 + pairwise exact%
  project   mean per-call cost from measured usage -> full-run projection
"""
import argparse
import itertools
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

OUT = Path("outputs/study_b/r5")
SEED = 202615


def canon(v) -> str:
    if isinstance(v, list):
        return "|".join(sorted(str(x).strip().casefold() for x in v))
    return str(v).strip().casefold()


def cmd_select() -> int:
    import pandas as pd
    h = pd.read_parquet("outputs/study_b/corpus/story_human_frozen.parquet")
    pool = json.loads(Path("outputs/study_b/r3/discovery_pool.json").read_text())["doc_ids"]
    eligible = sorted(set(h.doc_id) - set(pool))  # never QA on discovery docs
    rng = random.Random(SEED)
    picked = rng.sample(eligible, 12)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "cov_docs.json").write_text(json.dumps(
        {"seed": SEED, "doc_ids": picked[:2]}, indent=2))
    (OUT / "repeat_docs.json").write_text(json.dumps(
        {"seed": SEED, "doc_ids": picked[2:12]}, indent=2))
    print(f"cov: 2 docs (12 texts) | repeat: 10 docs (60 texts)")
    return 0


def load_answers(tag: str) -> dict:
    """(doc_id, source) -> {feature_id: canon(answer)}"""
    out = defaultdict(dict)
    f = OUT / f"answers_{tag}.jsonl"
    if not f.exists():
        return {}
    for l in open(f):
        r = json.loads(l)
        if "answers" in r:
            for fid, v in r["answers"].items():
                out[(r["doc_id"], r["source"])][fid] = canon(v)
    return dict(out)


def cmd_coverage() -> int:
    a, s = load_answers("cov_aspect"), load_answers("cov_single")
    n_feats = json.loads(Path("outputs/study_b/r5/n_features.json").read_text())["n"]
    texts = sorted(set(a) | set(s))
    cov_a = sum(len(a.get(t, {})) for t in texts) / max(1, len(texts) * n_feats)
    cov_s = sum(len(s.get(t, {})) for t in texts) / max(1, len(texts) * n_feats)
    agree = tot = 0
    for t in texts:
        for fid, v in a.get(t, {}).items():
            if fid in s.get(t, {}):
                tot += 1
                agree += (v == s[t][fid])
    rep = {"texts": len(texts), "features": n_feats,
           "coverage_aspect": round(cov_a, 4), "coverage_single": round(cov_s, 4),
           "cross_mode_agreement": round(agree / max(1, tot), 4)}
    (OUT / "coverage_report.json").write_text(json.dumps(rep, indent=2))
    print(json.dumps(rep))
    return 0


def cmd_alpha() -> int:
    runs = {i: load_answers(f"repeat_{i}") for i in range(1, 6)}
    # units: (text, feature) with >=2 run values
    values_by_unit = defaultdict(list)
    for i, data in runs.items():
        for t, feats in data.items():
            for fid, v in feats.items():
                values_by_unit[(t, fid)].append(v)
    units = {u: vs for u, vs in values_by_unit.items() if len(vs) >= 2}
    # Krippendorff nominal via coincidence matrix
    cooc = Counter()
    margins = Counter()
    n_pairable = 0
    for vs in units.values():
        m = len(vs)
        n_pairable += m
        for a, b in itertools.permutations(vs, 2):
            cooc[(a, b)] += 1 / (m - 1)
    for (a, b), c in cooc.items():
        margins[a] += c
    n = sum(margins.values())
    do = sum(c for (a, b), c in cooc.items() if a != b) / max(1e-9, n)
    de = 1 - sum((c / n) ** 2 for c in margins.values())
    alpha = 1 - do / max(1e-9, de)
    # mean pairwise exact agreement across runs
    pair_agree = []
    for i, j in itertools.combinations(range(1, 6), 2):
        a_, b_ = runs[i], runs[j]
        ag = tot = 0
        for t in set(a_) & set(b_):
            for fid in set(a_[t]) & set(b_[t]):
                tot += 1
                ag += (a_[t][fid] == b_[t][fid])
        if tot:
            pair_agree.append(ag / tot)
    rep = {"units": len(units), "alpha_nominal": round(alpha, 4),
           "mean_pairwise_exact": round(sum(pair_agree) / max(1, len(pair_agree)), 4),
           "gate": 0.8, "passes": alpha >= 0.8}
    (OUT / "repeatability_report.json").write_text(json.dumps(rep, indent=2))
    print(json.dumps(rep))
    return 0 if alpha >= 0.8 else 1


def cmd_project() -> int:
    tot_in = tot_out = calls = 0
    for f in OUT.glob("answers_*.jsonl"):
        for l in open(f):
            r = json.loads(l)
            u = r.get("usage")
            if u:
                tot_in += u["in"]; tot_out += u["out"]; calls += 1
    if not calls:
        raise SystemExit("no measured usage yet")
    from study_b.r5_apply import PIN, POUT
    per_call = (tot_in * PIN + tot_out * POUT) / 1e6 / calls
    import pandas as pd
    n_docs = len(pd.read_parquet("outputs/study_b/corpus/story_human_frozen.parquet"))
    n_dims = json.loads(Path("outputs/study_b/r5/n_features.json").read_text())["dims"]
    full_calls = n_docs * 6 * n_dims
    done = sum(1 for _ in open(OUT / "answers_full.jsonl")) if (OUT / "answers_full.jsonl").exists() else 0
    proj = (full_calls - done) * per_call
    spent = (tot_in * PIN + tot_out * POUT) / 1e6
    rep = {"measured_calls": calls, "mean_usd_per_call": round(per_call, 5),
           "spent_so_far_usd": round(spent, 2),
           "full_calls": full_calls, "already_done": done,
           "projected_remaining_usd": round(proj, 2)}
    (OUT / "cost_projection.json").write_text(json.dumps(rep, indent=2))
    print(json.dumps(rep))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["select", "coverage", "alpha", "project"])
    args = ap.parse_args()
    return {"select": cmd_select, "coverage": cmd_coverage,
            "alpha": cmd_alpha, "project": cmd_project}[args.cmd]()


if __name__ == "__main__":
    sys.exit(main())
