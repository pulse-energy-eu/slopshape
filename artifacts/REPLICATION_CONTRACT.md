# Replication contract - Russell et al. (2026), StoryScope

**The frozen ground truth of the study we replicate.** Every pipeline
parameter, prompt, model, and analysis choice is checked against this file.
Every row is either MATCH (we do what they did) or DEVIATION (with a stated
reason; the full deviation set is artifacts/DEVIATION_REGISTER.md, the
source of paper Tables 2 / E1).

## The reference record

The upstream pipeline is vendored as a working clone at `vendor/storyscope/`
(gitignored; re-created by `setup.sh`, which clones the upstream repository
at pinned commit `642e746` - pristine, including all 13 original prompts,
their model config, and their 304-feature fiction taxonomy - and applies our
declared deviations from `artifacts/our-fork.patch`). Drift is checked by
`.venv/bin/python -m study_b.verify_reference`, which fails loudly if the
clone leaves the pinned commit, the deviation set grows beyond the declared
plumbing files, or the model configuration drifts from the declared one.

## Their pipeline, stage by stage (source: their paper section 2 + released code)

| Stage | Their choice | Ours | Status |
|---|---|---|---|
| Human corpus | 10,272 Reddit fiction prompts | 2,250 pre-ChatGPT B2B blog posts, 268 domains, Wayback-provenanced | **DEVIATION (the point of the study)**: domain transfer fiction -> commercial nonfiction (D1) |
| Assignment extraction | Gemini 2.5 Flash infers a writing prompt from each human story | gemini-3-flash infers a content brief from each human post | DEVIATION: prompt adapted to nonfiction; newer Flash (2.5 deprecated). D2/D3 |
| Length instruction | Explicit `"approximately N words"` in every generation prompt | Same: `"Target length: about {target_words} words"`, target derived from the real post | **MATCH** |
| Generation models | GPT-5.4, Claude Sonnet 4.6, Gemini 3 Flash, DeepSeek V3.2, Kimi K2.5 | Identical five | **MATCH** |
| Generation system prompt | `"You are a creative writing expert who generates rich, detailed stories."` | Nonfiction equivalent, no "write like a human" coaching | DEVIATION: genre wording only |
| Stage 2 template extraction | GPT-5.1 in paper text / `gpt-5.4` in shipped config | `gpt-5.6-terra` via study_b/extract_templates.py | DEVIATION (D13): `gpt-5.4` failed the single-select agreement gate (0.747/0.759 vs the 0.80 bar); terra passed with zero unresolved failures |
| Stage 3 comparison pool | 600 stories over 100 prompts, blinded, source identities anonymized | Same design, 100 briefs; `gpt-5.6-terra`, high reasoning | MATCH (design) + DEVIATION (D13 model) |
| Stage 4 feature discovery | 3 runs, union, embedding dedup at cosine **0.85**, -> 304 features | Same procedure (3 terra runs -> union 457 -> answerability screen 282 -> dedup 266); dedup threshold 0.85 retained (D4) | **MATCH (procedure)** |
| Stage 5 feature application | Gemini 3 Flash, minimal thinking, one call per dimension | Same protocol; `gemini-3.6-flash` (D13) | MATCH (protocol) + DEVIATION (D13 model) |
| Encoding | Paper: one-hot nominal, multi-hot multi-select, ordinal by position | Per the paper's text (their released code deviated from it - defect B5 below; D9) | **MATCH (paper)** |
| Classifier | XGBoost, binary + 6-way, GroupKFold by prompt to prevent leakage | Same code; grouping by **domain** (blogs cluster by publisher - stronger control than theirs; D6) | MATCH + stricter |
| SHAP | Bootstrap B=50, prompt-level resampling -> core/fingerprint roles | Same | **MATCH** |
| Rarity percentile | Mean Euclidean distance to **25 nearest neighbors**, z-scored space, percentile vs train+val | `study_b/rarity.py` - our implementation of their definition (not in their released code; D7) | MATCH (verified: reproduces their human 0.71 / AI 0.49 pattern) |

## Their headline numbers (our fidelity targets)

Before any domain transfer, we replicated the original's fiction headline on
their own released data with our environment (M1 fidelity check):

| Metric | Their value | Ours |
|---|---|---|
| Binary human-vs-AI macro-F1 (narrative+style) | 96.0 | **96.17** on their data |
| Binary AUPRC | 0.982 | **0.983** on their data |
| 6-way attribution macro-F1 | 77.3 | **77.55** on their data |
| Narrative-only binary macro-F1 | 93.2 | 98.0 on our corpus - the study's headline (artifacts/r6/variant_results_parity.json) |
| Rarity: human mean / AI mean | 0.71 / 0.49 | 0.746 / 0.457 on their data (pattern replicates; our corpus d = 1.83) |
| Feature-assignment repeatability | Krippendorff alpha 0.90 | 0.891 on our corpus (artifacts/r5_gate/repeatability_report.json) |

## Length-confound protocol (their appendix; replicated in full)

They did not control length at generation time: an approximate-length
instruction, adherence reported, confound audited at analysis time. We
replicated all three audits; results in artifacts/r6/s9_fixes.json
(length_matched_faithful, length-only baseline) and parity_fixes.json
(p6_length_tertiles_f1), summarized in METHODOLOGY.md battery 8.4. Note on
direction: models regress toward their default output length - they
undershoot the original's ~6.2k-word targets and overshoot our ~1.15k-word
targets; the per-model ordering (GPT-5.4 and Claude long,
Gemini/DeepSeek/Kimi short) replicates in our measurements.

## Our fork: released-code defects and every deviation from upstream

`artifacts/our-fork.patch` is the exact diff of our fork against the pinned
upstream (7 files). It contains authentication/provider plumbing (gateway
provider with OpenAI-compatible base_url, Gemini API-key auth path,
multi-key rotation, configurable thinking budget) plus the five defects we
found in the original's released code, each fixed toward the paper's
*stated* method (paper Appendix I, Table I1):

| # | Defect in released code | Symptom | Our fix |
|---|---|---|---|
| B1 | Stage config keys passed twice to the provider layer | Every stage runner crashes on launch | De-duplicated the keyword pass-through (providers/base.py) |
| B2 | Stage 5 only recognizes a `human_story` source column | All human posts silently dropped: the feature matrix would contain zero human rows | Source-column handling accepts the corpus's human and mirror columns (5_feature_application/apply_features.py) |
| B3 | JSON-generation path ignores the thinking configuration | The paper states stage 5 runs "minimal thinking", but the released code sets no thinking budget and runs full reasoning (measured 183s vs 2.2s per dimension call, 83x) | `thinking_budget` set as a stage parameter, matching the paper's stated method (providers/vertex_provider.py) |
| B4 | Shipped stage-3 prompt does not implement the paper's stated method | The prompt asks for a two-template quality comparison and contains `{group_a_json}`/`{group_b_json}` placeholders the code never fills, while the paper describes all six templates presented together with cross-source divergence mining | Prompt rewritten to the paper's specification (all templates together, structured per-source notes, divergences, executive summary). The shipped original prompt is preserved pristine in the vendored clone's history at the pinned commit |
| B5 | Released encoding deviates from the paper's stated scheme (D9) | Ordinal and nominal features not encoded as the paper describes | Ordinal encoded by taxonomy position, nominal one-hot, per the paper's text |

MODEL DEVIATION (declared; D13): the intelligence-critical stages 3-4
(cross-source comparison, feature discovery; ~630 calls total) use
`gpt-5.6-terra` with `reasoning_effort=high`; stage 2 uses `gpt-5.6-terra`
(see the stage table); stage 5 uses `gemini-3.6-flash` with
minimal thinking. The five generator models are the paper's, unchanged.

Beyond these fixes and plumbing, no feature, encoding, classifier, or
analysis code in the vendored pipeline is modified.

## Drift check

Run `.venv/bin/python -m study_b.verify_reference` before any stage that
touches the pipeline. It verifies the pinned vendor commit, the declared
deviation set, the released fork patch coverage, and the declared model
configuration, failing loudly if any changed.
