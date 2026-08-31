# Code guide: rebuilding the study from the repository

The analysis code ships in study_b/ at the repository root; this file maps
every study stage to its entry point. Paths are relative to the repository
root. Scripts run as study_b modules from the root (e.g.
`.venv/bin/python -m study_b.r6_parity_fixes`); the rewording-durability
scripts (r7_*.py) are additionally included in this directory verbatim. The
vendored original pipeline is created locally at vendor/storyscope/ by
setup.sh (pristine upstream clone at the pinned commit 642e746) with our
declared fork deviations applied from artifacts/our-fork.patch (five
documented divergences between the original's released code and its paper,
each fixed toward the paper; paper Appendix I, source
artifacts/REPLICATION_CONTRACT.md).

## Environment

- Python virtualenv per setup.sh + requirements.txt (pinned to the versions that produced the paper's numbers; Python 3.12); XGBoost, SHAP, pandas, pyarrow for the analysis stages.
- API keys per env.example. Models used: gpt-5.6-terra and gpt-5.6-luna (OpenAI), gemini-3-flash and gemini-3.6-flash (Google), gpt-5.4, claude-sonnet-4.6, deepseek-v3.2, kimi-k2.5 (generators, via an AI gateway), F2LLM-4B embeddings (local, for dedup), gpt-5.4 (style audit).
- Gate before every stage: study_b/verify_reference.py fails loudly if the vendored pipeline leaves its pinned commit, the deviation set grows beyond the declared plumbing files, or the model configuration drifts from the declared one.
- Measured total spend for the full study: ~$1,650 at 2026 prices (corpus and funnel ~$27, briefs + mirrors ~$160, templates ~$660, discovery + screen ~$215, style audit ~$10, feature application ~$470, classification ~$0).

## Stage map

| Stage | Entry point | Output verified against |
|---|---|---|
| Corpus funnel + fetch + freeze (paper Table 1, steps 1-6) | see fetch/README.md | fetch/ledger.csv, fetch/* decision files |
| Briefs (2,250) | study_b/extract_briefs.py | gated |
| Mirrors (11,250) | study_b/generate_mirrors.py | gated |
| Template schema discovery | study_b/t0_schema_discovery.py | artifacts/TEMPLATE_SCHEMA_V2.md (PI-frozen) |
| Stage 2 templates (13,500) | study_b/extract_templates.py | gated |
| Stage 3 comparison | study_b/r3_pipeline_input.py then vendored 3_cross_source_comparison via study_b/r3_discovery.sh | gated intermediates |
| Stage 4 discovery + union | study_b/r3_discover_b2b.py, study_b/r3_union.py | instrument/taxonomy_union.json |
| Answerability screen | study_b/answerability_screen.py | instrument/taxonomy_screened.json + screen logs |
| Dedup 0.85 | study_b/r3_dedup.py | instrument/condensed_taxonomy_0.85.json |
| Style audit (3 runs) | study_b/r4_style_audit.py | instrument/style_excluded_features.json, artifacts/r5_gate/style_audit_summary.json |
| Stage 5 application (148,500 answers) | study_b/r5_apply.py | gated; sanity stats in artifacts/r5_gate/feature_sanity_report.json |
| Repeatability (5x60) | study_b/compare_repeatability.py | artifacts/r5_gate/repeatability_report.json |
| Encode + splits + freeze manifest | study_b/r6_build.py | artifacts/r6/splits.json, artifacts/FREEZE_MANIFEST_RUN2.md |
| Grid + training + variants + SHAP + CIs | study_b/r6_parity_fixes.py (faithful protocol: final models retrained on train+val, the paper's numbers) | artifacts/r6/variant_results_parity.json, parity_fixes.json |
| Core/fingerprint selection (value granularity) | study_b/r6_core_values.py | artifacts/r6/core_values_selection.json |
| Rarity | study_b/r6_rarity.py | artifacts/r6/rarity_report.json |
| Baselines | study_b/r6_baselines.py (the ModernBERT row came from a heavier rebuild script not included in the public release; its scores are committed in artifacts/r6/baselines.json) | artifacts/r6/baselines.json (+ s9_fixes.json reruns) |
| Six-way (faithful) + review batteries | study_b/r6_review_batch.py, study_b/r6_review2_fixes.py | artifacts/r6/review_batch.json, review2_fixes.json |
| Vertical heterogeneity + rarity tails (faithful) | study_b/r6_vertical_rarity.py | artifacts/r6/vertical_rarity_faithful.json |
| S9 reruns (direction-hypothesis package, exact memorization, baseline protocol fixes, length matching) | study_b/r6_s9_fixes.py | artifacts/r6/s9_fixes.json |
| Paper tables T6/T13-T16 | study_b/r6_paper_tables.py | artifacts/r6/PAPER_TABLES.md |
| Final figures | study_b/r6_figures_final.py | artifacts/figures/ |
| Rewording attack (1,450 self-rewrites) | study_b/r7_lamp_rewrite.py (copy: code/r7_lamp_rewrite.py; prompt: prompts/lamp_rewrite.md) | gated; gate record artifacts/r7/GATES.md |
| Rewrite gates (length drift, trivial copy, refusals, sampled claim check) | study_b/r7_verify_rewrites.py (copy: code/r7_verify_rewrites.py) | artifacts/r7/GATES.md, durability_aggregates.json (gates, attack_magnitude) |
| Claim-preservation census + QC loop (all 1,450 pairs) | study_b/r7_claim_census.py (copy: code/r7_claim_census.py) | artifacts/r7/GATES.md (census history), durability_aggregates.json |
| Rescoring with the frozen stage-5 instrument (15,950 answers) | study_b/r7_rescore.py (copy: code/r7_rescore.py) | gated; coverage stats in artifacts/r7/durability_aggregates.json (rescore) |
| Durability evaluation (frozen classifiers on the reworded split) | study_b/r7_durability_eval.py (copy: code/r7_durability_eval.py; asserts each classifier's recorded unattacked score before evaluating) | artifacts/r7/durability_aggregates.json |

The stage-3/4 batch runner (overnight orchestration with resume, spend
gates, and status files) is study_b/r3_discovery.sh; the remaining overnight
wrapper scripts are not included in the public release. Run parameters live
in the Python scripts themselves, not on the command line, so the committed
scripts are the run record.

## Protocol note

All paper numbers are from the FAITHFUL protocol (final models retrained on
train+val per the original; grids as recorded in
faithful numbers (r6_parity_fixes.py, r6_s9_fixes.py, r6_vertical_rarity.py,
r6_figures_final.py) assert the 0.9803 headline on refit; a diverging rebuild
fails loudly instead of silently producing different numbers.
