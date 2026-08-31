"""Rarity percentile - implemented exactly per Russell et al. (2026).

Not part of the released StoryScope code (verified); the paper defines it as:
z-score the encoded feature matrix, take each story's mean Euclidean distance
to its 25 nearest neighbors (excluding itself), and rank as a percentile
against the reference corpus (train+val in the paper's figure; --reference all
uses the full corpus, which we also report for robustness).

Fidelity targets from the paper: human mean 0.71 vs AI 0.49 (Cohen's d 0.83);
24.7% of human docs in the rarest decile vs 7.1% of AI; at prompt level the
human version ranks rarest 57.8% of the time.

Usage (from slop-benchmark/):
  .venv/bin/python -m study_b.rarity \
      --features vendor/storyscope/data/storyscope_features.parquet \
      --taxonomy vendor/storyscope/data/taxonomy.json \
      --out outputs/study_b/fidelity/rarity [--violin]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "vendor" / "storyscope"))

K_NEIGHBORS = 25


def compute_rarity(X: np.ndarray, reference_mask: np.ndarray) -> np.ndarray:
    """Mean Euclidean distance to the 25 nearest reference neighbors,
    excluding self, returned as percentile rank within the reference set."""
    from sklearn.neighbors import NearestNeighbors

    Xr = X[reference_mask]
    nn = NearestNeighbors(n_neighbors=K_NEIGHBORS + 1, algorithm="brute",
                          n_jobs=-1)
    nn.fit(Xr)
    # distances for every doc against the reference set
    dist, idx = nn.kneighbors(X, n_neighbors=K_NEIGHBORS + 1)
    # reference docs find themselves at distance 0 in slot 0; non-reference
    # docs keep their K nearest. Drop self-matches, keep 25.
    mean_dist = np.empty(len(X), dtype=np.float64)
    ref_indices = np.flatnonzero(reference_mask)
    pos_in_ref = {g: i for i, g in enumerate(ref_indices)}
    for i in range(len(X)):
        d = dist[i]
        self_pos = pos_in_ref.get(i)
        if self_pos is not None:
            mask = idx[i] != self_pos
            d = d[mask]
        mean_dist[i] = d[:K_NEIGHBORS].mean()
    # percentile vs the reference distribution of mean distances
    ref_sorted = np.sort(mean_dist[reference_mask])
    pct = np.searchsorted(ref_sorted, mean_dist, side="right") / len(ref_sorted)
    return pct


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", required=True)
    parser.add_argument("--taxonomy", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--reference", choices=["trainval", "all"],
                        default="trainval")
    parser.add_argument("--violin", action="store_true")
    args = parser.parse_args()

    from sklearn.model_selection import GroupKFold
    from storyscope.utils.feature_encoder import (
        build_feature_type_map, encode_features, filter_matched_prompts,
        load_features_parquet, load_taxonomy, build_groups,
    )

    tax = load_taxonomy(args.taxonomy)
    ftypes = build_feature_type_map(tax)
    df, feature_ids, authors = load_features_parquet(args.features, tax)
    df = filter_matched_prompts(df, authors)
    # mode="multi_hot" matches train_classifier.py exactly
    X, _cols = encode_features(df, feature_ids, ftypes, mode="multi_hot")
    X = np.asarray(X, dtype=np.float32)
    df = df.rename(columns={"author": "source"})

    # z-score over the corpus (constant columns -> 0)
    mu, sd = X.mean(axis=0), X.std(axis=0)
    sd[sd == 0] = 1.0
    X = (X - mu) / sd

    if args.reference == "trainval":
        # same deterministic first GroupKFold fold as train_classifier.py:
        # fold-1 test set is excluded; reference = train+val
        gkf = GroupKFold(n_splits=5)
        groups = build_groups(df)
        train_idx, _test_idx = next(gkf.split(X, np.zeros(len(X)), groups))
        ref = np.zeros(len(X), dtype=bool)
        ref[train_idx] = True
    else:
        ref = np.ones(len(X), dtype=bool)

    print(f"encoded {X.shape}, reference={ref.sum()} docs", file=sys.stderr)
    pct = compute_rarity(X, ref)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    res = df[["prompt_id", "source"]].copy()
    res["rarity_percentile"] = pct
    res.to_parquet(out / "rarity.parquet", index=False)

    human = res[res.source == "human"].rarity_percentile
    ai = res[res.source != "human"].rarity_percentile
    pooled_sd = np.sqrt((human.std() ** 2 + ai.std() ** 2) / 2)
    print("\n=== rarity fidelity vs paper ===")
    print(f"human mean: {human.mean():.3f}   (paper: 0.71)")
    print(f"AI mean:    {ai.mean():.3f}   (paper: 0.49)")
    print(f"Cohen's d:  {(human.mean() - ai.mean()) / pooled_sd:.2f}    (paper: 0.83)")
    thr = res.rarity_percentile.quantile(0.9)
    print(f"human in rarest decile: {(human > thr).mean() * 100:.1f}%  (paper: 24.7%)")
    print(f"AI in rarest decile:    {(ai > thr).mean() * 100:.1f}%  (paper: 7.1%)")
    per_source = res.groupby("source").rarity_percentile.mean().sort_values()
    print("\nper-source means:"); print(per_source.round(3).to_string())

    # prompt-level: how often is the human version the rarest of its prompt?
    wide = res.pivot_table(index="prompt_id", columns="source",
                           values="rarity_percentile")
    complete = wide.dropna()
    human_rarest = (complete.idxmax(axis=1) == "human").mean()
    print(f"\nhuman rarest per prompt: {human_rarest * 100:.1f}%  (paper: 57.8%)")

    if args.violin:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        order = ["human"] + [s for s in per_source.index[::-1] if s != "human"]
        data = [res[res.source == s].rarity_percentile for s in order]
        fig, ax = plt.subplots(figsize=(9, 5))
        parts = ax.violinplot(data, showmeans=True, widths=0.8)
        for pc in parts["bodies"]:
            pc.set_alpha(0.65)
        ax.set_xticks(range(1, len(order) + 1))
        ax.set_xticklabels(order)
        ax.set_ylabel("Rarity percentile (vs. train+val)")
        ax.set_title("Rarity percentile by source - fidelity replication of "
                     "Russell et al. (2026)")
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        fig.savefig(out / "violin.png", dpi=150)
        print(f"violin: {out / 'violin.png'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
