# Complete prompt set

Every LLM prompt used in the study, either as a file in this directory or as a
string constant in a released script (paths relative to the repository root).
Prompts embedded in scripts are referenced rather than copied so the released
script stays the single source of truth; each script holds its prompt as a
module-level constant near the top of the file. The one exception is the
stage-5 scoring prompt, which is additionally copied here verbatim because it
is the instrument's most load-bearing prompt (148,500 + 15,950 calls).

## Prompt files in this directory

| File | Stage |
|---|---|
| stage5_feature_application.md | Stage 5 feature application: the single scoring prompt (gemini-3.6-flash, minimal thinking, one call per post x dimension). Verbatim copy; source of truth is the PROMPT constant in study_b/r5_apply.py, imported unchanged by the rewording rescore (study_b/r7_rescore.py) |
| aspect_b2b_{purpose,audience,structure,explanation,evidence,voices,actionability,commercial,timeliness,pageformat,style}.md | Stage 4 feature DISCOVERY: one dimension-expert discovery prompt per schema dimension (gpt-5.6-terra, 3 runs; driven by study_b/r3_discover_b2b.py over the vendored pipeline's discovery stage). These propose candidate features from the stage-3 comparison data; they are not scoring prompts |
| cross_source_comparison_b2b.md | Stage 3 cross-source comparison (gpt-5.6-terra, high reasoning; the original's prompt with the dimension list swapped) |
| lamp_rewrite.md | Stage 6 rewording attack: span-level self-rewrite prompt targeting the seven LAMP artifact categories (each generator model rewrites its own posts); the header carries the prompt's iteration log |

## Prompts embedded in released scripts

| Prompt | Script (repository) | Model |
|---|---|---|
| Company-fit screen, funnel step 2 (company relevance, authorship-blind) | study_b/icp_screen.py | gpt-5.6-luna, 2 votes |
| Genre spot-check, funnel step 4 (informational-genre judgment; the deep-fetch filter chain in study_b/build_corpus.py imports the same GenreClassifier) | study_b/spot_check.py | gemini flash |
| Brief reverse-engineering (2-call design, anti-quotation clause) | study_b/extract_briefs.py | gemini-3-flash |
| Brief ablation variant without the anti-quotation clause | study_b/noaq_briefs.py | gemini-3-flash |
| Mirror generation (the generation instruction wrapping each brief) | study_b/generate_mirrors.py | the 5 generator models |
| Template schema discovery (bottom-up B2B structural dimensions) + consolidation | study_b/t0_schema_discovery.py | gpt-5.6-terra, 3 runs |
| Stage 2 template extraction against the frozen schema | study_b/extract_templates.py | gpt-5.6-terra |
| Stage 4 feature discovery (the dimension-expert prompt files above, injected into the vendored pipeline's discover_features.py by study_b/r3_discover_b2b.py) | prompts/aspect_b2b_*.md + study_b/r3_discover_b2b.py | gpt-5.6-terra |
| Stage 5 feature application (the file above) | study_b/r5_apply.py (PROMPT constant) | gemini-3.6-flash |
| Answerability screen | study_b/answerability_screen.py | gpt-5.6-terra, 2 votes |
| Style-dependence audit (3 runs, strict boundary) | study_b/r4_style_audit.py | gpt-5.4 |
| Rewording-attack system message (role-setting line editor) | study_b/r7_lamp_rewrite.py (copy: code/r7_lamp_rewrite.py) | the 5 generator models |
| Claim-preservation judge (same claims, no new facts) | study_b/r7_verify_rewrites.py (copy: code/r7_verify_rewrites.py; reused verbatim by the census) | gemini-3-flash |

The original's fiction-domain prompts, for comparison, are in the vendored
upstream pipeline at vendor/storyscope/storyscope/prompts/ (cloned pristine at
the pinned commit by setup.sh; our deviations are exactly
artifacts/our-fork.patch). The rejection logs produced by both
answerability-screen prompts are in instrument/.
