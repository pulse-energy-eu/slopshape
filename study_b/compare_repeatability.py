"""Compare two feature-extraction passes value-by-value, split by feature
type, against the pre-committed gate-1 thresholds:
  categorical/binary/multi_select: >=80% exact agreement
  ordinal/scale: >=95% within +-1 (exact also reported)

Usage: .venv/bin/python -m study_b.compare_repeatability PASS1_DIR PASS2_DIR
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

TAXONOMY = Path("vendor/storyscope/data/taxonomy.json")


def load_pass(d: str) -> dict[tuple, dict]:
    out = {}
    for f in glob.glob(f"{d}/*/*.features.json"):
        data = json.load(open(f))
        src = f.split("/")[-2]
        out[(data.get("prompt_id"), src)] = data.get("features", {})
    return out


def norm(v) -> str:
    if isinstance(v, list):
        return "|".join(sorted(str(x).strip().lower() for x in v))
    return str(v).strip().lower()


def main() -> int:
    p1, p2 = load_pass(sys.argv[1]), load_pass(sys.argv[2])
    docs = sorted(set(p1) & set(p2))
    import ast
    import re

    tax = json.load(open(TAXONOMY))
    ftype: dict[str, str] = {}
    ranks: dict[str, dict[str, int]] = {}
    for dim in tax["feature_taxonomy"].values():
        for aspect in dim.get("aspects", {}).values():
            for f in aspect.get("features", []):
                fid = f["id"]
                ftype[fid] = f.get("type", "categorical")
                if ftype[fid] in ("ordinal", "scale"):
                    try:
                        vals = ast.literal_eval(f.get("values", "[]"))
                        ranks[fid] = {norm(v): i for i, v in enumerate(vals)}
                    except (ValueError, SyntaxError):
                        ranks[fid] = {}
    n_num = sum(1 for t in ftype.values() if t in ("ordinal", "scale"))
    print(f"taxonomy: {len(ftype)} features, {n_num} ordinal/scale",
          file=sys.stderr)

    def to_rank(fid: str, v: str):
        """Rank of an ordinal/scale answer: taxonomy order, '3 - label'
        prefixes, or plain numbers."""
        if v in ranks.get(fid, {}):
            return ranks[fid][v]
        m = re.match(r"^(\d+(?:\.\d+)?)\s*(?:-|$)", v)
        if m:
            return float(m.group(1))
        try:
            return float(v)
        except ValueError:
            return None

    stats = {"cat_total": 0, "cat_exact": 0, "num_total": 0, "num_exact": 0,
             "num_close": 0}
    flips = []
    for key in docs:
        f1, f2 = p1[key], p2[key]
        for fid in set(f1) & set(f2):
            a, b = norm(f1[fid]), norm(f2[fid])
            if not a or not b or a == "none" or b == "none":
                continue
            t = ftype.get(fid, "categorical")
            if t in ("ordinal", "scale"):
                x, y = to_rank(fid, a), to_rank(fid, b)
                if x is None or y is None:
                    continue
                stats["num_total"] += 1
                stats["num_exact"] += x == y
                stats["num_close"] += abs(x - y) <= 1
                if abs(x - y) > 1:
                    flips.append((fid, t, a, b))
            else:
                stats["cat_total"] += 1
                stats["cat_exact"] += a == b
                if a != b:
                    flips.append((fid, t, a[:35], b[:35]))

    cat_pct = stats["cat_exact"] / max(stats["cat_total"], 1) * 100
    num_exact_pct = stats["num_exact"] / max(stats["num_total"], 1) * 100
    num_close_pct = stats["num_close"] / max(stats["num_total"], 1) * 100
    print(f"docs compared: {len(docs)}")
    print(f"categorical/binary/multi-select: {stats['cat_exact']}/"
          f"{stats['cat_total']} exact = {cat_pct:.1f}%  (threshold >=80%)")
    print(f"ordinal/scale exact:             {num_exact_pct:.1f}%")
    print(f"ordinal/scale within +-1:        {stats['num_close']}/"
          f"{stats['num_total']} = {num_close_pct:.1f}%  (threshold >=95%)")
    verdict = cat_pct >= 80 and num_close_pct >= 95
    print(f"\nGATE 1 REPEATABILITY: {'PASS' if verdict else 'FAIL'}")
    print("\nsample disagreements:")
    for f in flips[:10]:
        print("  ", f)
    return 0 if verdict else 1


if __name__ == "__main__":
    sys.exit(main())
