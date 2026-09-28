# SlopShape - methodology and results record

Companion methodology record for the paper "SlopShape: Identifying
AI-Generated Commercial Web Content". Every number in the paper appears here
in its methodological context; VERIFICATION.md maps each paper exhibit to the
released artifact that carries it and the script that regenerates it.

CONVENTIONS: this file records classification metrics as four-decimal
proportions (0.9695); the paper displays one-decimal percents (97.0). This
file numbers the validation batteries 8.1-8.22 in repository order (gaps are
prose exhibits); the paper presents nine numbered robustness checks
(its Table 8) plus prose exhibits - the mapping is in VERIFICATION.md. This
file keeps the working vocabulary (battery, freeze manifest, frozen); the
paper says check, committed/fixed/final. All classification numbers are from
the FAITHFUL protocol (final models retrained on train+val, per the
original); superseded train-only readings are noted where they existed.

Structure mirrors the original paper's methodology (Russell et al. 2026,
arXiv 2604.03136); deviations carry D-numbers (artifacts/
DEVIATION_REGISTER.md); referee-anticipated caveats carry R-numbers.

---

## 1. Research question and claims

The original showed AI-generated fiction is detectable from *structural*
choices (narrative architecture) rather than surface style. We ask whether
that finding survives transfer to **B2B blog content** - informational,
commercial, non-narrative prose.

Claims we make (scoped per R1/R2):
1. Unedited single-pass AI-generated B2B posts are detectable from structural
   features alone at high accuracy (headline below), with style features
   strictly excluded.
2. The original's secondary phenomena replicate: variant ordering
   (combined > structure > style), a small feature core carrying the signal,
   per-model structural fingerprints, and humans occupying rarer regions of
   structural feature space.
3. Effects are at least as large as the original's. WORDING RULE (R2):
   "consistent in direction, at least as large in magnitude, plausibly
   schema-fit-driven" - we do not claim the domain is intrinsically more
   separable.
4. (DURABILITY) The structural signal's behavior under a LAMP-parity
   rewording attack is MEASURED, not assumed: frozen classifiers,
   self-reworded test mirrors, humans unchanged. Headline durability deltas
   (unattacked -> attacked macro-F1): structural 0.9695 -> 0.9606 (-0.0090),
   style 0.8811 -> 0.8705 (-0.0106), all-features 0.9800 -> 0.9729
   (-0.0071). Section 6.5.

Claims we do NOT make: detection of edited/human-in-the-loop AI content (R1)
BEYOND the LAMP-parity rewording attack measured in section 6.5;
generalization beyond the five 2025-26 generator models; magnitude
comparability across domains; robustness to restructuring attacks or
commercial humanizer tools (future work, stated in the paper's limitations).

## 2. Data

### 2.1 Human corpus (theirs: 10,272 Reddit fiction prompts)

**2,250 human B2B blog posts** from **268 company domains**, published
2008-2022 (100% pre-ChatGPT snapshots via Wayback Machine; median 1,068
words). Funnel accounting (verified against the frozen parquet and the
committed ledger): 306 domains were SELECTED at the quota step (Table 1 step 5), of which 264 yielded
usable documents (40 fetch-empty, 2 emptied by the filter chain, total 42
empty); 4 replacement domains were drawn from the 307-domain keep-eligible
pool during the widen/backfill pass, giving the 268 corpus domains
(fetch/corpus_manifest.csv holds exactly 268 distinct domains: 264 from the
selected list plus carwoo.com, demandcurve.com, lovd.com, makeschool.com).
The per-domain keep-cap of 20 was enforced per fetch batch, not on the final
count - four domains exceed it via retry passes (max 29 docs; largest domain
share 1.29%). The 100-prompt discovery pool spans 82 of the 268 domains and
removes NO domain from the classification corpus (all 268 retain documents;
splits 198/32/38 train/val/test domains, domain-disjoint); the 11 pool
domains landing in test are the 8.15 sensitivity.

Sampling funnel (paper Table 1 steps 1-6, fully scripted, seeds committed; decision files in
fetch/): 15,075-domain composite frame (frozen composition per the committed
frame file: Inc5000 9,979 / YC directory 3,448 / FT1000 1,129 / G2 519; the
raw source lists were larger, with an anti-persona prefilter dropping 10.4%)
-> LLM ICP screen (gpt-5.6-luna, 2 votes, published prompt; 94.3% keep) ->
Wayback CDX qualification (698 qualified) -> genre spot-check (307
keep-eligible) -> vertical-quota selection (306; software cap 40%) ->
archive deep-fetch through the published filter chain (length 600-2,500
words, genre, language, near-duplicate) -> freeze.

Composition (final; reported transparently, R5):

| Axis | % |
|---|---|
| Verticals | software/SaaS 26.5, e-commerce 24.3, services 17.4, fintech 15.7, devtools 11.7, health 3.8, edtech 0.6 |
| Frame | YC 57.2, Inc5000 33.7, G2 6.8, FT1000 2.3 |
| Years | 2008-17: 8.5, 2018-19: 16.0, 2020-21: 41.9, 2022: 33.6 |

YC share passed its pre-set dilution gate (<58%) at the bar; defense = the
subset sensitivity (battery 8.6): headline holds within YC (0.988) and
non-YC (0.956) separately.

### 2.2 Brief reverse-engineering (their "mirror" mechanism, D2/D3)

Per post, a content brief is reverse-engineered (gemini-3-flash; adapted
prompt that names the publishing company as commissioner, with an
anti-quotation clause). 2,250/2,250 briefs, zero failures.

### 2.3 AI generation -> parallel corpus (generation models UNCHANGED)

The paper's five AI models: gpt-5.4, claude-sonnet-4.6, gemini-3-flash,
deepseek-v3.2, kimi-k2.5. **11,250 mirrors** (5 x 2,250), zero failures,
max_tokens 8,000 (D12, matched to B2B lengths). Known mismatch (R3): mirrors
run long (means: human 1,186; gpt 1,541; deepseek 1,447; gemini 1,283;
claude 1,279; kimi 1,064) - neutralized by the length-matched sensitivity
(8.4). Within-10%-of-source-length adherence per model (their Table 5
analogue): claude .66, kimi .47, gemini .41, deepseek .16, gpt .07 -
materially looser than the original's adherence; disclosed as a
mirror-fidelity parity gap and covered by 8.4.

### 2.4 Blinding and contamination exposure

Schema discovery saw human posts only. Feature discovery saw anonymized
author labels. Because the human posts predate the generating models' training
cutoffs, they are potentially IN the generating models' training data - that
exposure is exactly what the memorization battery bounds (8.16: 13-gram
0.19% of pairs, near-verbatim 0, filtered headline unchanged in substance);
the post-cutoff entity scan (8.5) additionally bounds anachronism leakage at
0.08%.

## 3. Pipeline (schema discovery + five stages + stage 6 durability)

**Schema discovery (NEW; D11): B2B-native template schema.** The fiction schema
(plot, characters...) misfits B2B posts. Three independent gpt-5.6-terra
runs over real human posts converged on an 11-dimension schema (purpose,
audience, structure and flow, explanation, evidence, voices, actionability,
commercial integration, timeliness, page format, writing style);
consolidated, gate-checked, frozen BEFORE stage 2
(artifacts/TEMPLATE_SCHEMA.md, incl. NarraBench mapping table). Discovery
ran on 18 stratified posts (fetch attrition from the 40-post target); the
three runs converged on near-identical systems, indicating saturation -
disclosed here, not only in the schema file. The mandated Writing-Style
bucket preserves the style firewall.

**Stage 2 - template extraction.** Model selected by a 2-round comparison:
gpt-5.6-luna failed the single-select agreement gate (0.747/0.759 vs 0.80;
terra self-consistency ceiling 0.884; gpt-5.4-mini eliminated at 0.681) ->
**gpt-5.6-terra** for all 13,500 templates (zero unresolved failures).

**Stage 3 - cross-source comparison.** Vendored pipeline, B2B comparison
prompt (dimension list swapped only), terra high reasoning, batches of 3,
34 batches over a 100-prompt (600-document) discovery pool (seeded,
stratified, EXCLUDED from all classifier splits).

**Stage 4 - feature discovery + screening + dedup.** 3 independent terra
runs x 11 dimension-expert prompts -> union **457 candidates** (theirs:
408). NEW quality gate: **answerability screen** (terra, strict 2-vote;
annotation-feasibility standard) -> **282 kept (38.3% rejected**, reasons
committed in instrument/; dominant defect: non-exhaustive value lists).
Caveat R6: the screen prompt was recalibrated once after a first run
rejected 95% on a philosophical-objectivity reading; both prompts, both
runs, and all reasons are preserved; the screen never sees labels. Dedup:
F2LLM-4B embeddings, single-linkage 0.85 (the original's published constant,
retained for parity) -> **266 features** (5.7%
merge; the original's own merge at 0.85 was 25.5% - their fiction candidate
pool was semantically denser; the threshold-sensitivity sweep is battery
8.12).

**Stage 5 - feature application.** gemini-3.6-flash, minimal thinking,
aspect-based (one call per text x dimension), single-select forcing.
**148,500 scoring calls (13,500 texts x 11 dims), zero failures, full matrix
verified.** Gates passed before scale-up: aspect-vs-single coverage 99.97%
vs 99.75% (8.8); mini-validation 39 OK / 1 AMBIGUOUS / **0 WRONG** on a
seeded 8x5 sheet; repeatability alpha 0.889 (5 runs x 60 texts over every
scored feature except the format-sensitive ones; gate 0.8; theirs 0.90).

**Style audit (strict boundary, R4).** GPT-5.4 rates all 266 features for
style dependence in 3 independent runs (exact 3-run agreement 0.989; rating
distribution low 219 / medium 19 / high 28); the strict rule excludes **34
features, all in the writing_style dimension**, leaving 232 narrative-strict
candidates pre-floor (artifact: artifacts/r5_gate/style_audit_summary.json;
human endorsement of the boundary: gold-session audit check, 8.2).

**Instrument floor (outcome-blind, pre-freeze).** Before any label-aware
analysis: 52 features excluded - 11 degenerate (>=98% one value; page chrome
unmeasurable in extracted text), 3 off-menu-prone (>2%), 38 unstable
(per-feature alpha < 0.6, the pre-set floor), leaving 214.

**Format-sensitivity filter (outcome-blind).** Human posts are scored as
extracted and normalized (the extracted text keeps the page title for some
posts only); AI posts are scored as generated, with a title line and
mostly markdown. A probe rescored three train+val samples with only the
format changed (study_b/r8_title_probe.py): 250 AI posts (50 per model)
through the corpus normalizer with the title kept as a plain first line
(A1), the same posts without the title line (A2), and 250 human posts whose
scored text has no title, with the stored title prepended (H1). A feature is
format-sensitive if the total variation distance between its original and
rescored answer distributions exceeds 2 x noise95 + 0.05 in any arm, where
noise95 is the 95th-percentile TVD between the full run and the repeat runs
(40 draws of 250 pairs, train+val docs). The rule was filed before the probe
was scored (artifacts/FILED_DECISIONS.md). It flags 11 structural features
and no style feature: PUR_OUT_003, AUD_PRB_002, COM_PLC_002, PAG_FUR_002,
PAG_NAV_003, PAG_NAV_004, PAG_NAV_005, PAG_NAV_007, PAG_NAV_008, ACT_STP_004,
STR_UNI_004 (evidence per feature: instrument/format_exclusions.json).
The same screen on the test split (confirmation only) flags 9, all among
the 11. **Final instrument: 203 features** (176 narrative-strict + 27 style;
theirs: 304 = 257 + 47).

**Stage 6 (DURABILITY): LAMP-parity rewording attack.** Adapts the
original's durability test (Chakrabarty et al. 2025 span-level rewriting;
their design: 278 Gemini stories, Gemini as its own rewriter, frozen
narrative classifier 93.9 F1 on edited vs 95.5 on originals = -1.6 points)
to commercial blog posts.

- ATTACK SET: all **1,450 test-split AI mirrors** (290 test prompts x 5
  models). SYMMETRIC SELF-REWRITE (D14): each of the five generator models
  rewrites its OWN posts - the original used one model only; our symmetric
  design removes that asymmetry and yields a per-model durability breakdown.
  The 290 human test posts are UNCHANGED.
- PROMPT (D15): LAMP's 7 AI-artifact categories plus their editing
  instructions, INSTRUCTION-ONLY - the original's 25 few-shot professional
  examples are fiction rewrites and do not transfer to B2B prose; dropping
  them is declared as domain adaptation, not parity. A content-preservation
  constraint is added (D16): keep claims, facts, and links; reword freely
  within them. Full prompt with its iteration log:
  prompts/lamp_rewrite.md.
- FREEZE DISCIPLINE: ALL classifiers frozen - deterministic refits of the
  committed models (no serialized weights are stored; each refit asserts its
  recorded number before evaluation); NO retraining on attacked text
  anywhere.
- VERIFICATION GATES (pass before any rescoring): (a) length drift of
  rewritten vs source mirror bounded (bound [0.6, 1.4] fixed in the harness
  before generation): 0 violations final (mean ratio 0.922, min 0.607);
  (b) claim-preservation: a seeded 50-pair gate proved too noisy at n=50
  (0.88 and 0.92 readings on near-identical samples), resolved by a full
  census of all 1,450 pairs: pre-QC 0.9034, after a two-pass regeneration
  QC loop (192 regenerations) post-QC census 0.9821 with 26 disclosed
  single-item residuals left in; (c) refusals: 0/1,450; trivial-copy flags
  0 after in-loop retries and reruns. Full gate record:
  artifacts/r7/GATES.md.
- RESCORING: stage-5 scorer unchanged (gemini-3.6-flash, minimal thinking,
  aspect-based, one dimension per call, single-select forcing) over the
  1,450 rewritten posts = **15,950 answers** (1,450 x 11 dims); frozen
  encoder; answers spliced into the test matrix in place of the original
  mirror rows (humans untouched). Coverage and failure counts reported like
  stage 5: 15,950/15,950 answers, 0 unresolved failures, off-option mean
  0.082% (original 0.089%), same 3 features >2% in both runs; encoding
  layout hard-asserted equal to the frozen 868-column matrix.
- EVALUATION: frozen structural (176), style-only (27), and all-features
  (203) classifiers on (unchanged humans + rewritten mirrors); macro-F1
  deltas overall and per generator model. Results: section 6.5; battery row
  8.21. Aggregates: artifacts/r7/durability_aggregates.json.

## 4. Feature space, variants, encoding (D9)

One-hot nominal/binary, multi-hot multi-select, ordinal position integers,
NaN missing (XGBoost-native). Matrix: **12,900 texts x 868 encoded columns**
for the 214 floor-surviving features (discovery pool excluded); the 203-feature
final instrument uses 840 of them. Variants: narrative-strict (HEADLINE,
176), style-only (27), all-features (203), core-only (9),
core+fingerprint (30).

## 5. Experimental protocol

artifacts/FREEZE_MANIFEST.md (hashes, seeds, grid, analysis list)
committed before training. Splits **domain-disjoint** at the paper's ratios
(D6, stricter than their random prompt split): 1,566 / 294 / 290 docs (seed
202616). Grid on val (108 binary configs over n_estimators/max_depth/
reg_lambda/scale_pos_weight, centered on their published constants incl.
lambda 2.0; the 6-way task gets its own 27-config grid centered on their
500/7/1.0). GRID PROVENANCE: these grids replaced the freeze-manifest grid
(which lacked the reg_lambda axis after a lambda-vs-learning-rate misread of
the original); the change, its parity motivation, and the exact executed
axes are recorded in the analysis manifest
(their protocol); all reported numbers from the held-out test split. Metrics
per metric-parity: binary macro-F1 + AUPRC; 6-way macro-F1 + accuracy. CIs:
10k bootstrap, prompt-level and domain-cluster (cluster primary).

## 6. Results

### 6.1 Binary detection (theirs: Table 2)

| Variant | n feat | Test macro-F1 | AUPRC | Original analogue |
|---|---|---|---|---|
| **Narrative-strict (headline)** | 176 | **0.9695** (cluster CI 0.955-0.983; prompt CI 0.957-0.981) | 0.9996 | 93.2 |
| Style-only | 27 | 0.8811 | 0.9944 | 85.8 |
| All features | 203 | 0.9800 | 0.9998 | 96.0 |
| Core-only | **9** | 0.9010 | 0.9967 | 30 feat -> 84.8 |
| Core+fingerprint | 30 | 0.9367 | 0.9978 | 101 -> 91.1 |

**Direction-hypothesis outcome:** the hypothesis predicted style-strict >
narrative-strict. The result is a SIGNIFICANT REVERSAL: narrative minus
style +8.8 pts - the hypothesis is REJECTED. Full
primary basis (artifacts/r6/s9_fixes.json, supersedes the prompt-only
CI [6.5, 11.4] of parity_fixes.json): domain-cluster CI [4.9, 13.2] (PRIMARY,
fixed in the freeze manifest), prompt CI [6.5, 11.3], document-level McNemar 20 vs 92
discordant (p = 3.2e-12), bootstrap two-sided p < 0.0001. The ORIGINAL
study's direction (structure > style) replicates, amplified (theirs +7.4).
The registered wording rule anticipated no significant reversal; that gap is
disclosed rather than papered over, and the paper never writes "confirmed"
against the registered direction. The TOST vs their 93.2 (band 91.2-95.2) is
DESCRIPTIVE: our CI [95.8, 98.1] lies above the band -
reported with the pre-committed R2 wording tier. Error-overlap diagnostic
(attached to the direction hypothesis): on the 1,740 test texts the structural model errs
29 times, the style model 101; only 9 errors are shared (Jaccard 0.07, kappa
0.12; binomial p < 0.001 on the asymmetric split) - the two instruments fail
on nearly disjoint documents, evidence they measure different signals.

Ordering combined > structure > style replicates exactly - CAVEAT (C4): our
style variant measures the fields of the single mandated Writing-Style
bucket by design; the ordering claim is conditional on that instrument and
is not presented as a clean replication of the original's style-narrative
asymmetry, whose style set emerged schema-wide.

### 6.1b Raw-text baselines (the original's Table 2 anchor)

| Baseline | Test macro-F1 | AUPRC |
|---|---|---|
| Length-only logistic | 0.4545 | 0.8706 (prevalence baseline 0.833 at the 5:1 ratio) |
| Stylometric + XGB (144-dim, their spec) | 1.0000 | 1.0000 |
| TF-IDF (1-2g, their 5,000-feature spec, full sweep) + XGB | 0.9927 | 1.0000 |
| ModernBERT-base fine-tune (512 tok, 3 ep, their config; train-only, single seed, disclosed) | 1.0000 | 1.0000 |
| Binoculars-STYLE (Qwen2.5-0.5B pair, disclosed substitute; train-only thresholding) | 0.7817 | 0.9797 |

BASELINE PROTOCOL: stylometric, TF-IDF, and length rows above are the
s9_fixes.json reruns - finals on train+val with the full 108-config sweep,
TF-IDF at the original's 5,000-feature spec (an earlier committed run used
50,000 features, fixed config, train-only; superseded, same 0.9927 to 4 dp).
ModernBERT and Binoculars-style remain train-only, disclosed in the paper.
Hyperparameter sensitivity: the original's published constants untuned give
binary 0.9656 / AUPRC 0.9994 and six-way 0.6860 / acc 0.6908 - within 0.004
of the tuned configs.

Reading: unedited single-pass generation is near-perfectly detectable from
surface signals in this corpus (stylometrics AND ModernBERT saturate at 1.0,
mirroring the original's 99.9/99.8; the stylometric set includes
formatting-sensitive counts, so part of that ceiling is formatting tells).
The replication-relevant statistic mirrors the original: structural features
RETAIN 97.0% of the surface ceiling (faithful headline 0.9695 / 1.0000;
theirs: 93.2 vs near-ceiling raw-text baselines); the superseded train-only
protocol reads 0.9643. Length alone fails. The Binoculars-style score
is a disclosed small-pair substitute (Qwen2.5-0.5B base/instruct vs their
Falcon-7B pair) and is not a parity point: it lands at 0.78 where their true
Binoculars failed at 55.9, so we report it as zero-shot-detector context
only, not as a replicated anchor.

### 6.2 Six-way attribution (theirs: Table 3)

Test macro-F1 0.6820, accuracy 0.6856 (own grid per Amendment 2; chance
16.7%; on par with the original's 68.4%). Per-class F1 (Table-11 parity):
human .944, gpt .793, gemini .624, deepseek .615, kimi .579, **claude .537**
(hardest).

### 6.3 Rarity (theirs: the violin figure)

Reference train+val, k=25, z-scored narrative-strict space:

| Statistic | Ours | Original |
|---|---|---|
| Human mean percentile | 0.835 | 0.71 |
| AI mean percentile | 0.436 | 0.49 |
| Cohen's d | **1.80** | 0.83 |
| Rarity AUC | 0.898 | 0.73 |
| Human rarest-of-prompt | 85.6% | 57.8% |
| Rarest decile (human/AI) | 47.3% / 3.0% | 24.7% / 7.1% |

Per-model AI means: deepseek 0.543 > claude 0.489 > gemini 0.456 > kimi
0.363 > gpt 0.330. Robust to reference=all (d 1.81).

Tail composition (their Table 12; artifact
artifacts/r6/vertical_rarity_faithful.json). Full-corpus basis (the basis of
the stats above): rarest 1% = 146 human vs 2 AI documents (98.7% human;
theirs, test basis: 42 vs 41); rarest 5% = 586 vs 85 (87.3%); rarest 10% =
1,016 vs 319 (76.1%). Test-only basis (the original's Table-12 basis, in the
same artifact): rarest 1% = 36 human vs 0 AI; 5% = 95 vs 17; 10% = 154 vs
64. BASIS NOTE (disclosed): our rarity statistics are computed over all
12,900 documents with the train+val percentile reference, not the original's
test-only basis; the test-only tails above show the gap is not a basis
artifact.

### 6.4 Top signal carriers (SHAP, 50-bootstrap)

Argument-structure stages, reader-address, temporal-framing and
sourcing-transparency features dominate; full top-20 in the released figure
f4_shap_top20 (artifacts/figures/).

### 6.5 Durability under rewording (theirs: the LAMP durability row)

Design in stage 6 (section 3). Evaluation basis: the 1,740-document test
split with the 1,450 mirrors replaced by their self-rewritten versions and
the 290 humans unchanged; all models frozen. Original anchor: their frozen
narrative classifier lost 1.6 F1 points (93.9 edited vs 95.5 originals,
Gemini-only arm).

| Classifier | Unattacked test | Reworded test | Delta |
|---|---|---|---|
| Structural (narrative-strict, 176) | 0.9695 | 0.9606 | -0.0090 |
| Style-only (27) | 0.8811 | 0.8705 | -0.0106 |
| All features (203) | 0.9800 | 0.9729 | -0.0071 |

Attacked structural macro-F1 95% CI: domain-cluster [0.9426, 0.9763]
(primary), prompt-level [0.9464, 0.9740] (10k resamples, seed 202616).
Flips AI->human of 1,450 attacked posts: structural 13, style-only 16,
all-features 8. Called human after rewording: structural 18 (9 before),
style-only 19 (8 before), all-features 10 (3 before).

Attack magnitude: surface phrasing largely replaced - mean surviving
13-gram share 0.269 across models (claude 0.535, deepseek 0.489, gpt 0.175,
kimi 0.141, gemini 0.003), i.e. ~73% of 13-word sequences no longer appear
verbatim; mean length ratio 0.922; and in a 20-post spot check 16.0% of all
measured feature answers changed (mean agreement 0.840; two scorings of the
same text differ on about 10.9%) - yet the
structural classifier's macro-F1 drops by less than one point. Self-rewrite rationale: each
model rewrote its own posts because that is the realistic production pattern
(a publisher polishing a draft uses the same model) and it removes the
original's single-model asymmetry.

Per-model structural macro-F1 on the reworded split (self-rewrite arm each):
gpt 0.9655, claude 0.9534, gemini 0.9586, deepseek 0.9586, kimi 0.9603.

Gate outcomes (stage-6 verification gates; full record
artifacts/r7/GATES.md): length drift 0 violations (bound [0.6, 1.4], fixed
in the harness before generation); claim-preservation census (all 1,450
pairs) post-QC 0.9821 (pre-QC 0.9034); refusals 0/1,450. Rescore coverage
15,950/15,950 answers.

Interpretation: structural detection moves little under the rewording attack
(-0.0090, CI containing the unattacked value) although the attack replaced
~73% of surface phrasing and changed 16.0% of the measured feature answers
in a 20-post spot check.
This matches the original's finding for its narrative
features (their -1.6 points, Gemini-only arm; ours -0.9 across all five
models, symmetric). Claims about paraphrase and humanizer attacks (which
optimize against detectors) remain scoped as future work, consistent with
the cited literature.

## 7. Core/fingerprint selection (theirs: section D, VALUE granularity)

Faithful procedure: B=50 prompt-resampled bootstrap SHAP at encoded-VALUE
granularity; criteria = top-quartile mean|SHAP| AND stability >= 0.55 AND
top25 >= 0.60 AND permutation-null exceedance (5 label-shuffles, 95th pct)
AND raw |human-AI value-mean gap| >= 0.20 AND cross-model AI spread <= 0.35.
Yields **10 core values on 9 core features** (theirs 33 values / 30
features) which ALONE test at **0.9010 macro-F1** (theirs: 30 features ->
84.8) and carry 25.6% of the structural model's attribution - the
small-core phenomenon replicates, sharper. Fingerprints from 6-way
per-class SHAP concentration (share >= 0.5 + null exceedance): 28 features
(human 17, gemini 4, gpt 3, deepseek 2, kimi 2, claude 0); core+fp (30)
tests at 0.9367.

Signed core directions (the paper's interpretive centerpiece): AI-leaning =
summary-or-synthesis closing stage, restated-thesis endings, no reader
participation pathway, modern or next-generation framing, confident
institutional explanation, mechanism-explanation stage; human-leaning = no
thesis before the first unit, no legacy-versus-modern contrast, historical
dates or periods, short (<800-word) pieces. AI writes the tidy
self-announcing essay; humans just write the thing.

## 8. Validation batteries and ablations

| # | Battery | Result | Status |
|---|---|---|---|
| 8.1 | Extractor repeatability | Over every scored feature except the 11 format-sensitive ones: alpha 0.889 (gate 0.8; theirs 0.90); mean pairwise Cohen kappa 0.888 (theirs 0.89); pairwise exact agreement 0.891 | DONE |
| 8.2 | Human validation (gold set) | Scoring on final annotations over the 19 draw features in the final instrument: human-human kappa 0.939 (orig 0.739), mean human-model kappa 0.951 (orig 0.839), 4/228 unclear flags (1.8%); style-boundary audit 90.0/97.5% vs model (bar 0.75; kappas 0.765/0.936), human-human 92.5%/0.827. ALL pre-filed bars passed | DONE |
| 8.3 | Mini-validation (pre-scale gate) | 39 OK / 1 AMBIGUOUS / 0 WRONG | DONE |
| 8.4 | Length confound (R3; theirs section F) | Decile-matched test subsample 1,545 docs (median words 1,003.5 human vs 1,081 AI); headline 0.9688 vs 0.9695 unmatched (their 93.2 -> 93.2 parity); rarity d 1.83; corr(words, rarity) 0.08; per-model matched rarity deepseek 0.546 > claude 0.492 > gemini 0.467 > kimi 0.373 > gpt 0.333 (full-corpus ordering preserved) | DONE |
| 8.5 | Post-cutoff entity scan | 0.08% pooled; faithful headline unchanged excluding flagged (0.9695) | DONE |
| 8.6 | Composition sensitivity (R5) | Faithful headline within YC 0.988 / non-YC 0.956; rarity gap in both | DONE |
| 8.7 | Temporal/era control | Era task at CHANCE (F1 0.491, grouped CV; 187 vs 1,622 posts, majority-class baseline 0.473); faithful orthogonality ablation flat (0.967-0.970); top-25 era/authorship overlap 3/25 | DONE |
| 8.8 | Aspect vs single-call | Coverage 99.97% vs 99.75%; cross-mode agreement 0.774 | DONE |
| 8.9 | Extraction-artifact ablation (R1) | Faithful headline minus all page-format features: 0.9642; minus timeliness too: 0.9652 | DONE (exploratory) |
| 8.10 | Split-seed sensitivity (R7) | 4 seeds, faithful protocol: 0.9579-0.9695 (mean 0.964, sample sd 0.005) | DONE (exploratory) |
| 8.11 | Template-vs-direct discovery ablation | Yield parity (raw 354 vs template-run mean 356.7, all 11 dims) BUT only ~23% bidirectional semantic overlap at 0.85 embedding similarity - the discovery pathway substantially shapes WHICH features are found. Template pathway is the one validated end-to-end (screen, alpha, gold kappas, headline); raw set not scored at scale (declared). Conclusion: templates are not a pass-through | DONE |
| 8.12 | Dedup-threshold sweep | Sweep 0.70-0.95 published: features 200/233/251/266/277/282, silhouette monotone decreasing (0.182 at 0.70 -> 0.065 at 0.85) - silhouette alone prefers lower thresholds; 0.85 RETAINED for parity with the original (our merge 5.7% vs the original's 25.5% at 0.85), sensitivity low. Divergence disclosed | DONE |
| 8.13 | Raw-text baselines (C1) | Length fails (0.45); stylometric 1.00; TF-IDF 0.993; ModernBERT 1.00 (their 512/3ep config; single seed disclosed); Binoculars-style substitute 0.78; structural retention 97.0% of ceiling (faithful) | DONE |
| 8.14 | Format-mismatch audit (C3) | Interview/transcript/roundup markers fire in 1-5% of humans, ~0% of mirrors (confound real but thin); headline on self-contained-page humans (86.5%): 0.9617. PROTOCOL NOTE: train-only (the marker column was floor-excluded from the frozen matrix); delta interpreted within that protocol | DONE |
| 8.15 | Discovery-pool domain overlap (C6) | 11 of 82 pool domains land in test; faithful sensitivity excluding them: 0.9648 | DONE |
| 8.16 | Memorization (C8, their section E, both rules) | EXACT IMPLEMENTATIONS (supersede a stride-sampled 13-gram scan and a span-less near-verbatim rule): 13-gram 20/10,750 pairs (0.19%; shuffled-human control 0.0%; per-model gemini 0.33% highest; theirs 0.70%); near-verbatim with span>=30 conjunct: 0 pairs; excluding all 16 affected prompts: headline 0.9725 (delta +0.0030; their filtered deltas <= +0.27) | DONE |
| 8.17 | Geometry (their dispersion finding) | Centroid distance 11.3; human dispersion 1.41x AI; mean 10-NN radius ratio human/AI 1.42 (direction replicates) | DONE |
| 8.18 | Vertical heterogeneity (Kruskal-Wallis) | FAITHFUL (refit reproduces headline 0.9695 exactly): H=9.047, p=0.107 over the 6 verticals with >=20 test docs - NOT significant, consistent with the original's null (H=4.69, p=0.46). Per-vertical macro-F1: services_other 0.9477, fintech_insurance 0.9626, ecommerce_retail 0.9633, devtools 0.983, software_saas 0.9954, health 1.0. The train-only computation (H=9.982, p=0.076) is not significant either. Artifact: artifacts/r6/vertical_rarity_faithful.json | DONE |
| 8.19 | Error-overlap diagnostic (direction hypothesis) | Structural errs 29/1,740, style 101/1,740, shared 9 (Jaccard 0.07, kappa 0.12, binomial p < 0.001) - near-disjoint failure sets | DONE |
| 8.20 | Learning curve | Train+val fractions 25/50/75/100%: 0.954 / 0.964 / 0.964 / 0.970 (3 seeds each) | DONE |
| 8.21 | LAMP-parity rewording durability (stage 6, section 6.5) | Structural -0.0090 (0.9695 -> 0.9606); style -0.0106; all-features -0.0071; per-model attacked structural gpt 0.9655, kimi 0.9603, gemini 0.9586, deepseek 0.9586, claude 0.9534; attack magnitude: ~73% of 13-grams replaced, 16.0% of feature answers changed; gates: length drift 0 violations, claim census post-QC 0.9821, refusals 0/1,450 | DONE |
| 8.22 | Format sensitivity (section 3, format-sensitivity filter) | Train+val probe (3 x 250 posts, filed rule) flags 11 structural features, 0 style; the test-split screen (250 AI posts; 235 human posts) flags 9, all among the 11. Final structural classifier on the test arms: 249/250 AI posts detected with markdown stripped, 247/250 with the title also removed; human posts called AI 15/235 with the title added vs 18/235 as scored. Artifacts: instrument/format_exclusions.json | DONE |

## 9. Instrument validity (the honesty section)

- The instrument is LLM-run end-to-end (R4): discovery terra, screen terra,
  scoring gemini-3.6-flash. Human ground truth = 8.3 (gate) + 8.2 (gold
  session PASSED, all bars exceeded).
- Screen recalibration (R6) disclosed in the methods body with both runs.
- Answer distributions, off-menu rates, per-feature stability all published
  (artifacts/r5_gate/feature_sanity_report.json).
- The mini-validation (8.3) is a GATE, not validation evidence: 40 items,
  non-blind interested scorer. Instrument validity claims rest on 8.1 and
  8.2.
- Reconciliations: the 52 floor exclusions = 11 degenerate + 3 off-menu +
  38 unstable AFTER overlap (an earlier log line said 40 unstable
  pre-overlap); the applied per-feature floor uses Krippendorff alpha,
  whereas the plan named AC1 - declared as an implementation substitution
  (same 0.6 bar, alpha is the stricter and more standard choice at 5
  raters).
  The grid/splits/seeds/analysis list were fixed in the manifest before
  training. The analysis manifest records the executed grids and why they
  replaced the manifest grid (reg_lambda parity).
- Gold-session operationalization: the extractor-vs-consensus bar
  is operationalized as the MEAN of the two per-annotator extractor kappas
  (0.951); both per-annotator kappas individually clear the 0.60 bar as
  well.
- Durability rescoring (stage 6) runs the IDENTICAL frozen stage-5
  instrument and scorer on the rewritten posts; the 8.1/8.2 validity
  evidence carries over to the reworded split only insofar as the scorer
  and prompts are byte-identical - that identity is asserted in the
  harness, and any scorer-model drift at rescore time was defined as a stop
  condition, not a footnote.
- Battery protocol basis: all batteries run under the faithful protocol
  except 8.14 (train-only, disclosed in its row). 8.18 was first computed
  train-only and recomputed faithfully (both readings in its row); 8.4's matching script was restored and the battery rebuilt
  faithfully after the original script was found lost.

## 10. Limitations

**Competing interests.** The author operates Sitefire, a commercial GEO/AEO
product, and plans a content-scoring product informed by this line of work.
Analysis constants were frozen before any classifier was trained
(artifacts/FREEZE_MANIFEST.md), and the gold-set bars were filed before
annotation (artifacts/FILED_DECISIONS.md). The methods, instrument, prompts,
code, and aggregate artifacts are publicly released, with document-level
data available to researchers on request, so its claims can be verified
independently of that interest. Both gold-set annotators are affiliated with
the company; the annotation protocol (independence, encoded-basis scoring,
pre-filed bars, unclear-flag reporting) is designed to constrain that bias
and is disclosed.

**Release posture.** Tiered release: PUBLIC = sampling ledger +
deterministic fetch pipeline (no redistribution of copyrighted post texts),
template schema + NarraBench mapping, full 203-feature instrument
(definitions, answer menus, exclusion records), complete prompt set (incl.
both screen prompts + rejection reasons and the rewording-attack prompt),
analysis code + fork patch + the durability harness and gate code, freeze
manifest, filed decision records, aggregate result artifacts (incl. the
durability aggregates and gate record), regeneration scripts. GATED
(researchers on request, non-commercial research agreement) = per-document
feature answers (from 148,500 scoring calls + 15,950 rescoring calls), exact model refits
(no serialized weights are stored anywhere; the released code refits each
model deterministically and asserts the reported headline), briefs (2,250),
mirrors (11,250), rewritten mirrors (1,450). Rationale: commercial interest
makes the ready-to-use scoring assets product substrate; mirrors and
rewrites derive from copyrighted sources. Everything gated is rebuildable
from the public release.

**Durability scope.** The measured attack is LAMP-style span-level rewording
only (stage 6, section 6.5, battery 8.21, deviations D14-D16). What remains
out of scope and is stated as future work in the paper: restructuring
attacks (reordering sections, merging or splitting arguments, stripping
scaffolding) and commercial humanizer tools. The durability experiment
postdates the main run; its design, gates, and freeze discipline were fixed
before generation.

R1 scope (unedited single-pass generation, plus LAMP-style reworded
single-pass generation as measured in section 6.5); R2 magnitude
interpretation; corpus 2,250 vs 10,272 with YC-heavy frame (57.2%) and 75%
of posts from 2020-2022; single-team replication; restructuring attacks and
humanizer tools untested (declared future work).

## Figures inventory (released renders in artifacts/figures/)

| Paper figure | Content | File |
|---|---|---|
| Figure 1a | Pipeline schematic (two-row flow) | f1_pipeline.png |
| Figure 1b | Rarity violin by source | f2_rarity_violin.png |
| Figure 2 | 6-way confusion matrix | f5_confusion6.png |
| Figure 3 | Top-20 SHAP features (plain-language names) | f4_shap_top20.png |
| Figure A1 | Length boxplots by source | f7_lengths.png |
| Figure F2 | LDA projection | f6_lda.png |
| (supplementary) | Variant bars vs original anchors + headline CI | f3_variants.png |

Generated by study_b/r6_figures_final.py (one consistent design system,
captions in artifacts/figures/CAPTIONS.md); the figure refit reproduces the
reported six-way 0.682 exactly, asserted in the script. Generated paper
tables (instrument composition, core-value tables, fingerprints) are in
artifacts/r6/PAPER_TABLES.md.
