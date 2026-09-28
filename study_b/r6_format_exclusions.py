#!/usr/bin/env python
"""Format-sensitivity filter: the last step of the instrument floor.

Human posts are scored as extracted and normalized; generated posts are
scored as produced, with a title line and markdown. The train+val probe
(study_b/r8_title_probe.py screen --split trainval; rule filed in
artifacts/FILED_DECISIONS.md of the release package) flags the features whose
answers move with that format difference. This step removes them from every
variant set written by study_b/r6_build.py and records the evidence. The
test-split screen, when present, is recorded as confirmation and never
changes the set.

Outputs (outputs/study_b/r6/):
  format_exclusions.json  excluded ids with per-feature evidence (noise95,
                          threshold, TVD per arm, flagging arms) and the
                          test-split confirmation
  variant_sets.json       narrative_strict / style_only / all_features with
                          the format-sensitive features removed

  .venv/bin/python -m study_b.r6_format_exclusions
"""
import json
import sys
from pathlib import Path

R6 = Path("outputs/study_b/r6")
TRAINVAL = Path("outputs/study_b/r8_trainval_probe/screen.json")
TEST = Path("outputs/study_b/r8_trainval_probe/test_confirmation.json")


def format_sensitive() -> set:
    """Feature ids removed by the format-sensitivity filter."""
    return set(json.load(open(R6 / "format_exclusions.json"))["excluded"])


def main() -> int:
    tv = json.load(open(TRAINVAL))
    assert tv["split"] == "trainval" and tv["n_features_screened"] == 214
    excluded = sorted(tv["flagged"])
    evidence = {r["feature"]: {k: r[k] for k in ("style", "noise95",
                                                 "threshold", "tvd",
                                                 "flag_arms")}
                for r in tv["features"] if r["flagged"]}
    sets = json.load(open(R6 / "variant_sets.json"))
    sets = {k: [f for f in fids if f not in set(excluded)]
            for k, fids in sets.items()}
    out = {"source": str(TRAINVAL), "rule": tv["rule"],
           "n_per_arm": tv["n_per_arm"],
           "excluded": excluded, "n_excluded": len(excluded),
           "n_structural_excluded": sum(not evidence[f]["style"]
                                        for f in excluded),
           "n_style_excluded": sum(evidence[f]["style"] for f in excluded),
           "evidence": evidence,
           "variant_counts": {k: len(v) for k, v in sets.items()}}
    if TEST.exists():
        te = json.load(open(TEST))
        assert te["split"] == "test"
        tflag = set(te["flagged"])
        out["test_confirmation"] = {
            "source": str(TEST), "n_per_arm": te["n_per_arm"],
            "flagged_test": sorted(tflag),
            "both": sorted(tflag & set(excluded)),
            "trainval_only": sorted(set(excluded) - tflag),
            "test_only": sorted(tflag - set(excluded)),
            "note": "confirmation only; never changes the exclusion set"}
    json.dump(out, open(R6 / "format_exclusions.json", "w"), indent=1)
    json.dump(sets, open(R6 / "variant_sets.json", "w"), indent=1)
    print(json.dumps({k: out[k] for k in ("excluded", "variant_counts")}),
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
