"""Drift check against the pinned replication reference.

Fails loudly if (a) the vendored working clone (vendor/storyscope, created by
setup.sh) no longer sits on the pinned upstream commit, (b) our deviation set
from upstream grew beyond the plumbing files declared in
artifacts/REPLICATION_CONTRACT.md, or (c) the vendored config/models.yaml no
longer matches the declared run configuration (the paper's models plus the
declared stage-3/4 model deviation; artifacts/REPLICATION_CONTRACT.md).

Run before any stage that touches the pipeline:
  .venv/bin/python -m study_b.verify_reference
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PINNED = "642e746804e1ee4138ffdcf13b7412eb3dc2a70b"
PATCH = Path("artifacts/our-fork.patch")

# files our fork is ALLOWED to touch (plumbing only, per the contract)
ALLOWED = {
    "config/models.yaml",
    "storyscope/providers/base.py",
    "storyscope/providers/openai_provider.py",
    "storyscope/providers/vertex_provider.py",
    "storyscope/2_template_extraction/extract_templates.py",
    "storyscope/5_feature_application/apply_features.py",
    "storyscope/prompts/cross_source_comparison.md",
    "storyscope/4_feature_discovery/cluster_features.py",
    "storyscope/4_feature_discovery/discover_features.py",
    "storyscope/4_feature_discovery/build_taxonomy.py",
    "storyscope/utils/feature_encoder.py",
}

# vendored config/models.yaml stage -> substring the configured model must
# contain, plus extra per-stage requirements. This encodes the DECLARED run
# configuration: stages 3-4 on gpt-5.6-terra with high reasoning (declared
# model deviation, artifacts/REPLICATION_CONTRACT.md), stage 5 on Gemini
# Flash with minimal thinking (the paper's stated method, defect B3 fix).
STAGE_MODELS = {
    "cross_source_comparison": "gpt-5.6-terra",
    "feature_discovery": "gpt-5.6-terra",
    "feature_application": "gemini-3-flash",
}


def check_models(vendor: Path) -> int:
    import yaml
    cfg = yaml.safe_load((vendor / "config/models.yaml").read_text())["pipeline"]
    bad = 0
    for stage, must_contain in STAGE_MODELS.items():
        got = str(cfg.get(stage, {}).get("model", ""))
        if must_contain not in got:
            print(f"MODEL DRIFT: {stage} = {got!r}, declared config requires "
                  f"{must_contain!r}", file=sys.stderr)
            bad += 1
    for stage in ("cross_source_comparison", "feature_discovery"):
        eff = str(cfg.get(stage, {}).get("reasoning_effort", ""))
        if eff != "high":
            print(f"MODEL DRIFT: {stage} reasoning_effort = {eff!r}, "
                  f"declared config requires 'high'", file=sys.stderr)
            bad += 1
    if cfg.get("feature_application", {}).get("thinking_budget") != 0:
        print("MODEL DRIFT: feature_application must use minimal thinking "
              "(thinking_budget: 0), per the paper's stated method",
              file=sys.stderr)
        bad += 1
    if not bad:
        print(f"models: {len(STAGE_MODELS)} stages match the declared "
              "configuration")
    return bad


def main() -> int:
    problems: list[str] = []

    vendor = Path("vendor/storyscope")
    if not vendor.exists():
        print("vendor/storyscope absent - run setup.sh first", file=sys.stderr)
        return 1

    # (a) vendored clone on the pinned commit
    head = subprocess.run(["git", "-C", str(vendor), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    if head != PINNED:
        problems.append(f"vendor clone at {head[:12]}, expected {PINNED[:12]}")
    else:
        print(f"vendor clone: on pinned commit {PINNED[:12]}")

    # (b) deviation set unchanged
    diff = subprocess.run(
        ["git", "-C", str(vendor), "diff", "--name-only", PINNED,
         "--", "storyscope", "config"],
        capture_output=True, text=True).stdout.split()
    touched = set(diff)
    extra = touched - ALLOWED
    if extra:
        problems.append("fork touches files outside the declared plumbing "
                        f"set: {sorted(extra)}")
    print(f"fork deviations: {len(touched)} file(s), "
          f"{'all declared' if not extra else 'UNDECLARED PRESENT'}")

    # (c) the applied deviation matches the released fork patch: every file
    # the released patch touches must be touched in the working clone
    if PATCH.exists():
        patched = {ln.split(" b/")[-1].strip()
                   for ln in PATCH.read_text().splitlines()
                   if ln.startswith("diff --git ")}
        missing = patched - touched
        if missing:
            problems.append("released fork patch not (fully) applied; "
                            f"unapplied files: {sorted(missing)} "
                            "(run setup.sh)")
        else:
            print(f"fork patch: all {len(patched)} patched files present in "
                  "the working clone's deviation set")
    else:
        problems.append(f"missing {PATCH}")

    if problems:
        print("\nDRIFT DETECTED:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        print("\nResolve (usually: rerun setup.sh), or update "
              "artifacts/REPLICATION_CONTRACT.md deliberately.",
              file=sys.stderr)
        return 1
    print("\nOK: no drift from the replication reference.")
    if check_models(vendor):
        print("\nFAIL: model configuration drifted from the declared "
              "configuration.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
