#!/usr/bin/env python
"""Final paper-styled figures (F1-F6) regenerated from committed artifacts.

One consistent design system across all figures: fixed per-source palette,
uniform typography, no truncated labels, PNG 300dpi + vector PDF, captions
written alongside. Output: outputs/study_b/r6/results/figures/final/

  .venv/bin/python -m study_b.r6_figures_final
"""
import json
import sys
import textwrap
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

OUT = Path("outputs/study_b/r6/results")
FIG = OUT / "figures" / "final"
SEED = 202616

# ---- design system ---------------------------------------------------------
HUMAN = "#2f4fc4"
MODEL_C = {"gpt": "#e8590c", "claude": "#e6a23c", "gemini": "#2f9e44",
           "deepseek": "#9c36b5", "kimi": "#74808c"}
AI_FILL = "#d9dde2"
INK = "#1f2430"
GRID = "#e6e8ec"
LABELS = {"human": "Human", "gpt": "GPT-5.4", "claude": "Claude Sonnet 4.6",
          "gemini": "Gemini 3 Flash", "deepseek": "DeepSeek V3.2",
          "kimi": "Kimi K2.5"}
SHORT = {"human": "Human", "gpt": "GPT-5.4", "claude": "Claude 4.6",
         "gemini": "Gemini 3", "deepseek": "DeepSeek 3.2", "kimi": "Kimi 2.5"}
ORDER = ["human", "gpt", "claude", "gemini", "deepseek", "kimi"]

CAPTIONS = {}


def style(ax, grid_axis="y"):
    ax.spines[["top", "right"]].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(INK)
    ax.tick_params(colors=INK, labelsize=9.5)
    if grid_axis:
        ax.grid(axis=grid_axis, color=GRID, linewidth=0.7, zorder=0)
        ax.set_axisbelow(True)


def save(fig, name, caption):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / f"{name}.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIG / f"{name}.pdf", bbox_inches="tight")
    CAPTIONS[name] = caption
    print(f"saved {name}", flush=True)


def feature_names():
    tax = json.loads(Path("outputs/study_b/r3/dedup/condensed_taxonomy_0.85.json").read_text())
    names = {}
    def walk(x):
        if isinstance(x, dict):
            if "id" in x and "name" in x:
                names[x["id"]] = x["name"]
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(tax)
    return names


# ---- F1 pipeline schematic -------------------------------------------------
def f1_schematic(plt):
    fig, ax = plt.subplots(figsize=(12.4, 3.6), dpi=160)
    ax.set_xlim(0, 100); ax.set_ylim(0, 30); ax.axis("off")
    rows = [
        # (x, y, w, title, sub)
        (1, 16.5, 17, "Human corpus", "2,250 posts, 268 domains\npre-2023 archive snapshots"),
        (21, 16.5, 17, "Brief mirroring", "reverse-engineered briefs\n5 AI models, 11,250 mirrors"),
        (41, 16.5, 17, "Templates", "11-dim commercial schema (fixed)\n13,500 extractions"),
        (61, 16.5, 17, "Feature discovery", "3 runs, 457 candidates\nscreen 282, dedup 266"),
        (81, 16.5, 18, "Scoring", "148,500 LLM answers\nalpha 0.89, gold kappa 0.93+"),
        (1, 1.5, 17, "Instrument floor", "outcome-blind exclusions\n214 features final"),
        (21, 1.5, 17, "Encoding + splits", "868 columns, domain-disjoint\nmanifest fixed pre-training"),
        (41, 1.5, 17, "Classification", "XGBoost variants, SHAP core\nheadline macro-F1 0.980"),
        (61, 1.5, 17, "Rewording test", "each AI post rewritten by\nits own model, F1 unchanged"),
        (81, 1.5, 18, "Validation checks", "robustness + validity checks\nall complete"),
    ]
    for x, y, w, title, sub in rows:
        fc = "#eef1fb" if y > 10 else "#f6f7f9"
        ax.add_patch(plt.Rectangle((x, y), w, 11, facecolor=fc, edgecolor=INK,
                                   linewidth=0.9, zorder=2))
        ax.text(x + w / 2, y + 8.4, title, ha="center", va="center",
                fontsize=9.2, fontweight="bold", color=INK, zorder=3)
        ax.text(x + w / 2, y + 3.9, sub, ha="center", va="center",
                fontsize=6.8, color="#444b58", zorder=3)
    arr = dict(arrowstyle="-|>", color=INK, linewidth=1.1,
               shrinkA=2, shrinkB=2)
    for x0 in (18, 38, 58, 78):
        ax.annotate("", xy=(x0 + 3, 22), xytext=(x0, 22), arrowprops=arr)
    for x0 in (18, 38, 58, 78):
        ax.annotate("", xy=(x0 + 3, 7), xytext=(x0, 7), arrowprops=arr)
    # orthogonal connector: Scoring (top row) down into Instrument floor
    mid = 14.5
    ax.plot([90, 90], [16.5, mid], color=INK, linewidth=1.1, zorder=1)
    ax.plot([90, 9.5], [mid, mid], color=INK, linewidth=1.1, zorder=1)
    ax.annotate("", xy=(9.5, 12.5), xytext=(9.5, mid),
                arrowprops=dict(arrowstyle="-|>", color=INK, linewidth=1.1,
                                shrinkA=0, shrinkB=1))
    save(fig, "f1_pipeline",
         "Study pipeline. Top row: corpus construction and measurement "
         "(human corpus, brief-mirrored AI counterparts, template extraction, "
         "feature discovery with answerability screen and dedup, LLM scoring). "
         "Bottom row: outcome-blind instrument floor, encoding with "
         "domain-disjoint splits, classification, the rewording test, and "
         "the validation checks.")
    plt.close(fig)


# ---- F2 rarity violin ------------------------------------------------------
def f2_violin(plt):
    import pandas as pd
    r = pd.read_parquet(OUT / "rarity" / "rarity.parquet")
    col = "rarity_trainval"
    fig, ax = plt.subplots(figsize=(8.6, 4.6), dpi=160)
    data = [r[r.source == s][col].dropna().to_numpy() for s in ORDER]
    vp = ax.violinplot(data, showextrema=False, widths=0.82)
    for body, s in zip(vp["bodies"], ORDER):
        body.set_facecolor(HUMAN if s == "human" else AI_FILL)
        body.set_edgecolor(INK); body.set_linewidth(0.8)
        body.set_alpha(0.95 if s == "human" else 0.9)
    for i, (d, s) in enumerate(zip(data, ORDER)):
        m = float(np.mean(d))
        c = "white" if s == "human" else MODEL_C.get(s, INK)
        ax.hlines(m, i + 0.74, i + 1.26,
                  color=(INK if s != "human" else "white"), linewidth=1.6, zorder=4)
        ax.text(i + 1, 1.045, f"{m:.2f}", ha="center", fontsize=9.5,
                color=(HUMAN if s == "human" else INK))
    ax.axhline(0.5, color="#b9bfc9", linestyle=(0, (4, 3)), linewidth=0.9)
    ax.set_xticks(range(1, 7))
    ax.set_xticklabels([SHORT[s] for s in ORDER], fontsize=9.5)
    ax.set_ylabel("Structural rarity percentile", fontsize=10.5, color=INK)
    ax.set_ylim(-0.02, 1.1)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    style(ax)
    ax.set_title("Human posts occupy the rare regions of structural space",
                 fontsize=12, color=INK, pad=14)
    save(fig, "f2_rarity_violin",
         "Structural rarity percentile by source (k=25 nearest neighbors in "
         "the z-scored narrative-strict feature space, train+val reference; "
         "bars mark source means). Humans concentrate in the rarest regions "
         "(mean 0.84 vs pooled AI 0.44; Cohen's d = 1.83; original: 0.71 vs "
         "0.49, d = 0.83).")
    plt.close(fig)


# ---- F3 variants vs original ----------------------------------------------
def f3_variants(plt):
    v = json.load(open(OUT / "variant_results_parity.json"))
    cv = json.load(open(OUT / "core_values_selection.json"))
    bars = [
        ("Style only\n(27 feat)", v["style_only"]["test"]["macro_f1"], 0.858, None),
        ("Core only\n(10 feat)", cv["variants"]["core_only"]["test"]["macro_f1"], 0.848, None),
        ("Core + fingerprint\n(33 feat)", cv["variants"]["core_fp"]["test"]["macro_f1"], 0.911, None),
        ("Structural\n(187 feat, headline)", v["narrative_strict"]["test"]["macro_f1"], 0.932,
         v["narrative_strict"].get("test_ci")),
        ("All features\n(214 feat)", v["all_features"]["test"]["macro_f1"], 0.960, None),
    ]
    fig, ax = plt.subplots(figsize=(8.6, 4.6), dpi=160)
    xs = np.arange(len(bars))
    for i, (lab, ours, orig, ci) in enumerate(bars):
        accent = "headline" in lab
        ax.bar(i, ours, width=0.62, color=HUMAN if accent else "#93a5e8",
               edgecolor=INK, linewidth=0.7, zorder=3)
        if ci:
            lo, hi = ci["domain_cluster"]["ci95"]
            ax.errorbar(i, ours, yerr=[[ours - lo], [hi - ours]], fmt="none",
                        ecolor=INK, elinewidth=1.3, capsize=4, zorder=5)
            ax.text(i, hi + 0.005, f"{ours:.3f}", ha="center",
                    fontsize=9.5, color=INK, fontweight="bold")
        else:
            ax.text(i, ours + 0.006, f"{ours:.3f}", ha="center", fontsize=9.5,
                    color=INK, fontweight="bold")
        ax.scatter(i, orig, marker="D", s=42, facecolor="white",
                   edgecolor=INK, linewidth=1.2, zorder=6)
        ax.text(i, orig - 0.017, f"{orig:.3f}", ha="center", fontsize=8,
                color="#444b58")
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    handles = [Patch(facecolor="#93a5e8", edgecolor=INK,
                     label="This study (B2B)"),
               Line2D([], [], marker="D", linestyle="none", markersize=7,
                      markerfacecolor="white", markeredgecolor=INK,
                      label="Original study (fiction)")]
    ax.legend(handles=handles, frameon=False, fontsize=9.5, loc="upper left")
    ax.set_xticks(xs)
    ax.set_xticklabels([b[0] for b in bars], fontsize=9.5)
    ax.set_ylabel("Test macro-F1 (human vs AI)", fontsize=10.5, color=INK)
    ax.set_ylim(0.8, 1.005)
    style(ax)
    ax.set_title("Detection by feature variant, against the original's anchors",
                 fontsize=12, color=INK, pad=12)
    save(fig, "f3_variants",
         "Binary detection macro-F1 on the held-out domain-disjoint test "
         "split, by feature variant (bars; final models retrained on "
         "train+val per the original's protocol; error bar = 10k "
         "domain-cluster bootstrap CI on the headline). Diamonds mark the "
         "original study's corresponding fiction-domain results. Ordering "
         "combined > structural > style replicates; every variant lands above "
         "its original analogue. Y-axis starts at 0.80.")
    plt.close(fig)


# ---- F4 SHAP top20 ---------------------------------------------------------
def f4_shap(plt):
    d = json.load(open(OUT / "shap_core_selection.json"))
    names = feature_names()
    ms = sorted(d["mean_shap"].items(), key=lambda kv: -kv[1])[:20]
    labs = []
    for fid, _ in ms:
        nm = names.get(fid, fid)
        labs.append(textwrap.fill(nm, 34) + f"\n({fid})")
    vals = [v for _, v in ms]
    fig, ax = plt.subplots(figsize=(8.4, 8.6), dpi=160)
    ys = np.arange(len(ms))[::-1]
    ax.barh(ys, vals, height=0.62, color="#93a5e8", edgecolor=INK,
            linewidth=0.6, zorder=3)
    cv = json.load(open(OUT / "core_values_selection.json"))
    core_feats = set(cv.get("core_features") or
                     [str(c).split("__")[0] for c in cv.get("core_values", [])])
    for y, (fid, v) in zip(ys, ms):
        if fid in core_feats:
            ax.barh([y], [v], height=0.62, color=HUMAN, edgecolor=INK,
                    linewidth=0.6, zorder=4)
    ax.set_yticks(ys)
    ax.set_yticklabels(labs, fontsize=8.2, color=INK)
    ax.set_xlabel("Mean |SHAP| (50-bootstrap mean, aggregated per feature)",
                  fontsize=10.5, color=INK)
    style(ax, grid_axis="x")
    ax.set_title("Top-20 structural features separating human from AI posts",
                 fontsize=12, color=INK, pad=12)
    save(fig, "f4_shap_top20",
         "Top-20 features of the structural (narrative-strict) classifier by "
         "bootstrap-mean absolute SHAP contribution, labeled with their "
         "plain-language instrument names (feature IDs in parentheses; full "
         "question wording in the released instrument). Dark bars mark the ten core features (Section 6).")
    plt.close(fig)


# ---- F5 confusion + F6 LDA (need a quick refit on frozen splits) ----------
def f5_f6(plt):
    from study_b.r6_train import load, cols_for
    from study_b.r6_parity_fixes import fit
    from sklearn.metrics import confusion_matrix
    import xgboost as xgb

    df, variants = load()
    cols = cols_for(df, variants["narrative_strict"])
    trval = df[df.split.isin(["train", "val"])]
    te = df[df.split == "test"]

    # F5: 6-way confusion (their published 500/7/1.0-centered protocol)
    # exact grid-selected config from the parity run (P3): the figure must
    # reproduce the reported 0.7917 model
    cfg6 = json.load(open(OUT / "parity_fixes.json"))[
        "p2_core_fingerprint"].get("sixway_config") or \
        {"n_estimators": 250, "max_depth": 5, "reg_lambda": 1.0}
    m6 = xgb.XGBClassifier(random_state=SEED, n_jobs=-1, tree_method="hist",
                           eval_metric="mlogloss",
                           **{k: v for k, v in cfg6.items()
                              if k in ("n_estimators", "max_depth",
                                       "reg_lambda", "learning_rate")})
    src_order = ["human", "gpt", "claude", "gemini", "deepseek", "kimi"]
    ymap = {s: i for i, s in enumerate(src_order)}
    m6.fit(trval[cols], trval.source.map(ymap))
    pred = m6.predict(te[cols])
    from sklearn.metrics import f1_score
    mf1 = f1_score(te.source.map(ymap), pred, average="macro")
    assert abs(mf1 - 0.7917) < 0.005, f"6-way refit {mf1:.4f} != reported 0.7917"
    print(f"6-way refit macro-F1 {mf1:.4f} (reported 0.7917)", flush=True)
    cm = confusion_matrix(te.source.map(ymap), pred, normalize="true") * 100
    fig, ax = plt.subplots(figsize=(6.4, 5.6), dpi=160)
    im = ax.imshow(cm, cmap="Blues", vmin=0, vmax=100)
    for i in range(6):
        for j in range(6):
            ax.text(j, i, f"{cm[i, j]:.0f}", ha="center", va="center",
                    fontsize=9.5,
                    color="white" if cm[i, j] > 55 else INK)
    ax.set_xticks(range(6)); ax.set_yticks(range(6))
    ax.set_xticklabels([LABELS[s] for s in src_order], rotation=35,
                       ha="right", fontsize=8.6)
    ax.set_yticklabels([LABELS[s] for s in src_order], fontsize=8.6)
    ax.set_xlabel("Predicted", fontsize=10.5, color=INK)
    ax.set_ylabel("True", fontsize=10.5, color=INK)
    ax.set_title("Six-way source attribution (row %)", fontsize=12,
                 color=INK, pad=10)
    fig.colorbar(im, ax=ax, shrink=0.8, label="Row %")
    save(fig, "f5_confusion6",
         "Row-normalized test confusion of the six-way source-attribution "
         "model (macro-F1 0.792 vs 16.7% chance). Humans are near-perfectly "
         "separated; the residual confusion is AI-vs-AI, hardest for "
         "DeepSeek V3.2.")
    plt.close(fig)

    # F6: LDA projection
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
    X = np.nan_to_num(df[cols].to_numpy(dtype=np.float32), nan=0.0)
    mu, sd = X.mean(0), X.std(0); sd[sd == 0] = 1
    Z = LinearDiscriminantAnalysis(n_components=2).fit_transform(
        (X - mu) / sd, df.source)
    fig, ax = plt.subplots(figsize=(7.6, 5.8), dpi=160)
    for s in ["gemini", "deepseek", "kimi", "claude", "gpt", "human"]:
        mk = (df.source == s).to_numpy()
        ax.scatter(Z[mk, 0], Z[mk, 1], s=5,
                   alpha=0.5 if s == "human" else 0.35,
                   c=HUMAN if s == "human" else MODEL_C[s],
                   label=LABELS[s], linewidths=0, rasterized=True)
    leg = ax.legend(frameon=False, fontsize=9, markerscale=2.6,
                    loc="upper right")
    for lh in leg.legend_handles:
        lh.set_alpha(1)
    ax.set_xlabel("LD1", fontsize=10.5, color=INK)
    ax.set_ylabel("LD2", fontsize=10.5, color=INK)
    style(ax, grid_axis=None)
    ax.set_title("LDA projection of the structural feature space",
                 fontsize=12, color=INK, pad=10)
    save(fig, "f6_lda",
         "Two-component LDA projection of the encoded structural feature "
         "space (12,900 documents). Human posts (blue) separate along LD1; "
         "the five AI models overlap heavily with each other, consistent "
         "with the original's geometry finding (human dispersion 1.42x AI).")
    plt.close(fig)


def main() -> int:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": INK,
                         "axes.labelcolor": INK, "figure.facecolor": "white"})
    f1_schematic(plt)
    f2_violin(plt)
    f3_variants(plt)
    f4_shap(plt)
    f5_f6(plt)
    (FIG / "CAPTIONS.md").write_text(
        "# Final figure captions (S8 draft input)\n\n" +
        "\n".join(f"**{k}**: {v}\n" for k, v in CAPTIONS.items()))
    print("FIGURES FINAL DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
