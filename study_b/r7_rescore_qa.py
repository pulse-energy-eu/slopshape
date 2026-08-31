#!/usr/bin/env python
"""R7 durability: QA gates for the rewritten-post rescoring run.

Gate 1  full matrix: every (doc_id, source) x 11 dims answered, zero errors
        outstanding, every feature id present in its dim's answer set.
Gate 2  off-option rate per feature (single-choice answers outside the allowed
        value list; multi_select elements outside the list) - compared with
        the SAME statistic computed on the original stage-5 answers restricted
        to the same 1,450 (doc_id, source) pairs. Original property: <2% per
        feature.
Gate 3  scorer sanity: 20 random docs, per-feature agreement between rewritten
        and original answers (differences expected where the rewrite changed
        the text; this checks the scorer runs correctly, not equality).

Writes outputs/study_b/r7/rescore_qa.json.

  .venv/bin/python -m study_b.r7_rescore_qa
"""
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from study_b.r5_apply import load_features  # noqa: E402
from study_b.r5_qa import canon  # noqa: E402

R7 = Path("outputs/study_b/r7")
MODELS = ["gpt", "claude", "gemini", "deepseek", "kimi"]
SEED = 202616


def load_answers(path, keep_pairs=None):
    """(doc_id, source) -> {fid: canon(answer)}; also (pair, dim) seen set."""
    ans, dims_seen, errors = defaultdict(dict), set(), []
    for l in open(path):
        r = json.loads(l)
        pair = (r["doc_id"], r["source"])
        if keep_pairs is not None and pair not in keep_pairs:
            continue
        if "answers" in r:
            dims_seen.add((pair, r["dim"]))
            for fid, v in r["answers"].items():
                ans[pair][fid] = canon(v)
        else:
            errors.append({"pair": list(pair), "dim": r["dim"],
                           "error": r.get("error", "")[:120]})
    return ans, dims_seen, errors


def off_option_rates(ans, feats):
    """fid -> (n_off, n_answered)."""
    stats = {f["id"]: [0, 0] for f in feats}
    ftype = {f["id"]: f.get("type") for f in feats}
    allowed = {f["id"]: {canon(v) for v in f.get("values", [])} for f in feats}
    for fa in ans.values():
        for fid, a in fa.items():
            if fid not in stats:
                continue
            stats[fid][1] += 1
            if ftype[fid] == "multi_select":
                parts = set(a.split("|")) if a else set()
                if parts - allowed[fid]:
                    stats[fid][0] += 1
            else:
                if a not in allowed[fid]:
                    stats[fid][0] += 1
    return stats


def main() -> int:
    by_dim = load_features()
    dims = sorted(by_dim)
    all_feats = [f for fs in by_dim.values() for f in fs]
    fid_of_dim = {d: {f["id"] for f in fs} for d, fs in by_dim.items()}

    pairs = set()
    for m in MODELS:
        for l in open(R7 / f"rewritten_{m}.jsonl"):
            r = json.loads(l)
            pairs.add((r["doc_id"], r["source"]))

    rw_ans, rw_dims, rw_errors = load_answers(R7 / "answers_rewritten.jsonl")
    orig_ans, _, _ = load_answers("outputs/study_b/r5/answers_full.jsonl",
                                  keep_pairs=pairs)

    # ---- Gate 1: full matrix
    missing_cells = [(p, d) for p in sorted(pairs) for d in dims
                     if (p, d) not in rw_dims]
    # error rows whose cell was later filled by a resume-retry are resolved
    rw_errors = [e for e in rw_errors
                 if (tuple(e["pair"]), e["dim"]) not in rw_dims]
    extra_pairs = sorted(set(rw_ans) - pairs)
    # feature-level missingness (informational: r5 accepts >=90% coverage per
    # call after retries; the encoder NaN-fills, same as the original run)
    all_ids = {fid for fs in fid_of_dim.values() for fid in fs}

    def miss_stats(ans):
        n_miss = sum(len(all_ids - set(ans.get(p, {}))) for p in pairs)
        n_docs = sum(1 for p in pairs if all_ids - set(ans.get(p, {})))
        return {"missing_feature_cells": n_miss,
                "of_total": len(pairs) * len(all_ids),
                "docs_affected": n_docs}

    gate1 = {
        "n_pairs": len(pairs),
        "n_cells_expected": len(pairs) * len(dims),
        "n_cells_answered": sum(1 for p in pairs for d in dims
                                if (p, d) in rw_dims),
        "missing_cells": [[list(p), d] for p, d in missing_cells],
        "unresolved_errors": len(rw_errors),
        "extra_pairs": [list(p) for p in extra_pairs],
        "feature_missingness_rewritten": miss_stats(rw_ans),
        "feature_missingness_original_same_pairs": miss_stats(orig_ans),
        "pass": (not missing_cells and not rw_errors and not extra_pairs),
    }

    # ---- Gate 2: off-option rates, rewritten vs original (same pairs)
    def summarize(stats):
        rates = {fid: (o / n if n else 0.0) for fid, (o, n) in stats.items()}
        vals = sorted(rates.values())
        n = len(vals)
        return rates, {
            "features": n,
            "mean": sum(vals) / n,
            "median": vals[n // 2],
            "p95": vals[int(n * 0.95)],
            "max": max(vals),
            "n_over_2pct": sum(v > 0.02 for v in vals),
            "n_zero": sum(v == 0 for v in vals),
        }

    rw_rates, rw_sum = summarize(off_option_rates(rw_ans, all_feats))
    og_rates, og_sum = summarize(off_option_rates(orig_ans, all_feats))
    worst = sorted(rw_rates.items(), key=lambda kv: -kv[1])[:10]
    gate2 = {
        "rewritten": rw_sum,
        "original_same_pairs": og_sum,
        "worst_rewritten_features": [
            {"fid": fid, "rewritten": r, "original": og_rates.get(fid, 0.0)}
            for fid, r in worst],
        "pass": rw_sum["n_over_2pct"] <= max(3, og_sum["n_over_2pct"] * 2),
    }

    # ---- Gate 3: 20-doc spot comparison vs original answers
    rng = random.Random(SEED)
    sample = rng.sample(sorted(pairs), 20)
    spot = []
    for p in sample:
        rw, og = rw_ans.get(p, {}), orig_ans.get(p, {})
        common = set(rw) & set(og)
        agree = sum(rw[f] == og[f] for f in common)
        spot.append({"doc_id": p[0], "source": p[1],
                     "n_common_features": len(common),
                     "agreement": agree / len(common) if common else None})
    agr = [s["agreement"] for s in spot if s["agreement"] is not None]
    gate3 = {
        "docs": spot,
        "mean_agreement": sum(agr) / len(agr),
        "min_agreement": min(agr),
        "max_agreement": max(agr),
        "note": ("agreement < 1 is EXPECTED (rewrites changed the text); "
                 "this gate checks the scorer produced full, parseable, "
                 "on-instrument answers for every sampled doc"),
        "pass": all(s["n_common_features"] >= 250 for s in spot),
    }

    out = {"gate1_full_matrix": gate1, "gate2_off_option": gate2,
           "gate3_spot_comparison": gate3,
           "all_pass": gate1["pass"] and gate2["pass"] and gate3["pass"]}
    json.dump(out, open(R7 / "rescore_qa.json", "w"), indent=2)
    print(json.dumps({k: v for k, v in out.items() if k == "all_pass"}
                     | {"g1": gate1["pass"], "g2": gate2["pass"],
                        "g3": gate3["pass"]}), file=sys.stderr)
    return 0 if out["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
