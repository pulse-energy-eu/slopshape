# SlopShape - release package

Companion package for the paper "SlopShape: Identifying AI-Generated
Commercial Web Content" (Jochen Madler, Sitefire; arXiv preprint
forthcoming; working titles until 2026-08-25 referenced B2B blog content
and a StoryScope replication framing - same study, every number unchanged).
It contains everything needed to verify every number in the paper and to
rebuild the study end to end, without redistributing any copyrighted post
text.

License (LICENSE file): the code (study_b/, code/, setup.sh,
requirements.txt, env.example) is released under the PolyForm Noncommercial
License 1.0.0; everything else is all rights reserved, public for
verification and audit. Researchers who want to reuse the instrument,
prompts, or data files beyond verification, need a commercial code license,
or need the gated document-level data (per-document feature answers, briefs,
mirrors, model refits), can request access under a non-commercial research
agreement: jochen@sitefire.ai.

## The study

StoryScope (Russell et al. 2026, arXiv 2604.03136) showed AI-generated
fiction is detectable from discourse-level structural choices alone (93.2
macro-F1), with a small feature core, per-model fingerprints, and human
stories occupying rarer regions of structural space. We replicate the full
pipeline on a domain with none of fiction's machinery: 2,250 pre-ChatGPT
human B2B blog posts (268 company domains, Wayback Machine snapshots) paired
with 11,250 AI mirrors from the same five generator models, measured with a
B2B-native 214-feature structural instrument frozen before analysis.

Findings: structural features alone reach 98.0 test macro-F1 (95%
domain-cluster CI 96.7-99.2) on domain-disjoint splits; the structural and
style instruments fail on nearly disjoint documents (19 vs 101 test errors, 4
shared); every secondary phenomenon replicates, consistent in direction and
larger in magnitude - variant ordering (98.1 > 98.0 > 88.1), a 10-feature
core at 93.5, six-way source attribution at 79.2 (chance 16.7), and an
amplified human rarity gap (Cohen's d 1.83 vs the original's 0.83). The
structural signal survives rewording: with every AI test post rewritten by
its own model, structural detection is unchanged (98.0 -> 98.1 macro-F1).
A human gold session validates the LLM-run instrument (human-human kappa
0.928, human-model 0.946). Claims are scoped to single-pass generation
from the five studied AI models, both as generated and after rewording.

## What is in this package

| Path | Content |
|---|---|
| MANIFEST.md | Complete file inventory with sha256 checksums and the gated-items list |
| VERIFICATION.md | Number-by-number map from every paper exhibit to its artifact and regeneration script |
| artifacts/ | Canonical methodology and results record, freeze manifest, template schema with NarraBench mapping, deviation register, replication contract, fork patch, all aggregate result JSONs (incl. the rewording-durability aggregates and gate record under artifacts/r7/), gold-session results, instrument QA records, rendered figures |
| instrument/ | The 214-feature instrument in full: candidate union (457), both answerability-screen outputs with per-feature rejection reasons, deduped taxonomy (266, with definitions and answer menus), style-boundary and instrument-floor exclusion records |
| prompts/ | The complete prompt set: the stage-5 scoring prompt, the stage-4 discovery prompts, the stage-3 comparison prompt, the rewording-attack prompt with its iteration log, and a map to every prompt embedded in the released scripts |
| fetch/ | Corpus reconstruction: the full sampling ledger (URLs, Wayback snapshot ids, per-document filter outcomes) and every funnel decision file, steps 1-5 |
| study_b/ | The analysis pipeline: every regeneration script named in VERIFICATION.md and code/README.md, from corpus funnel to durability evaluation |
| code/ | Guide mapping every study stage to its entry point, plus verbatim copies of the rewording-durability harness and gate scripts (r7_*.py) |
| setup.sh, requirements.txt, env.example | Environment bootstrap: pinned virtualenv, pinned upstream clone of the original pipeline (vendor/storyscope) with artifacts/our-fork.patch applied, API-key names |
| LICENSE | PolyForm Noncommercial 1.0.0 for the code; all rights reserved for the rest |

The analysis scripts ship in study_b/ at the repository root; the vendored
original pipeline is created locally by setup.sh (a pristine clone of the
upstream StoryScope repository at its pinned commit, with our declared
deviations applied from artifacts/our-fork.patch). Nothing else is required.

## What is gated, and why

Per-document feature answers (148,500, plus the 15,950 rescored answers of
the rewording test), trained model weights, briefs (2,250), mirrors
(11,250), and the rewritten test mirrors (1,450) are available to
researchers on request under a
non-commercial research agreement; MANIFEST.md lists them with sizes. Two
reasons, stated in the paper's competing-interests section: the authors
operate Sitefire, a commercial GEO/AEO product, and plan a content-scoring
product informed by this work, which makes the ready-to-use scoring assets
direct product substrate; and the mirrors embed content derived from
copyrighted source posts. Everything gated is rebuildable from this public
release. Request process: email jochen@sitefire.ai; access is granted under
a non-commercial research agreement.

## How to verify the paper

1. Look up any paper number in VERIFICATION.md; open the named artifact file.
2. Check integrity: every data file's sha256 is in MANIFEST.md, and the pre-training freeze manifest's hash chain (taxonomy, exclusions, style boundary, splits) is verifiable in-package - commands in instrument/README.md.
3. To recompute rather than read: the regeneration script named in VERIFICATION.md rebuilds the artifact; the faithful-protocol scripts assert the 0.9803 headline on refit and fail loudly on divergence. Recomputation of classifier numbers requires the gated encoded matrix or a full rebuild (below).

## How to rebuild from scratch

0. Environment: run setup.sh (pinned virtualenv from requirements.txt; clones the pinned upstream pipeline into vendor/storyscope and applies artifacts/our-fork.patch; verifies with study_b/verify_reference.py).
1. Corpus: replay fetch/ledger.csv against the Wayback Machine (deterministic; no LLM calls; fetch/README.md). Full funnel re-run from the frames is also scripted, seeds committed in-script.
2. Generation: briefs then mirrors with the five generator models (study_b/extract_briefs.py, study_b/generate_mirrors.py; ~$160 at 2026 prices).
3. Measurement: schema is frozen (artifacts/TEMPLATE_SCHEMA_V2.md); templates, comparison, discovery, screen, dedup, and application per code/README.md (~$1,350; gpt-5.6-terra, gemini-3.6-flash, F2LLM-4B embeddings).

Measured total cost of the original run was ~$1,650. Model availability
caveat: the pipeline pins 2026 model versions by exact name; a rebuild after
provider deprecation is a new measurement, not a verification.

## License

See the LICENSE file. The code directories - study_b/, code/, plus setup.sh,
requirements.txt, and env.example - are licensed under the PolyForm
Noncommercial License 1.0.0 (noncommercial research use permitted;
commercial use by separate agreement). Everything else in the package - the
artifacts, instrument, prompts, fetch data, manifest, documentation, and
figures - remains all rights reserved, published for verification and audit,
with reuse available to researchers on request (jochen@sitefire.ai). The
vendored original pipeline (created locally by setup.sh, not distributed
here) retains its upstream license.

## Citation

[PLACEHOLDER - citation and DOI at publication.]

Please also cite the original study this work replicates: Russell et al.
(2026), StoryScope: Investigating idiosyncrasies in AI fiction, arXiv
2604.03136.
