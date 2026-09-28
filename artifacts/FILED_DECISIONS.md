# Filed decision records

Three decisions were written down with a date before the data they govern
existed. Dates are commit dates in the author's working repository. All other
analysis constants were frozen in artifacts/FREEZE_MANIFEST.md (2026-08-16)
before any classifier was trained.

## Gold-set acceptance bars (filed 2026-08-17, before any annotation)

Gold session sample: seed 202617, annotation pack committed 2026-08-16.
Scoring on the encoded basis. Bars:

- Annotator vs annotator (question answerability): Cohen's kappa >= 0.60
- Extractor vs human consensus (instrument fidelity): Cohen's kappa >= 0.60

Cells answered "unclear - none of these fits" by either annotator are excluded
from kappa and reported separately as instrument flags. A below-bar outcome is
reported as such and does not modify the instrument.

Outcome: human-human kappa 0.928, mean human-model kappa 0.946
(artifacts/gold/GOLD_RESULTS.json).

## Executed hyperparameter grids (filed 2026-08-20)

The grids executed for the faithful-protocol results differ from the grid in
artifacts/FREEZE_MANIFEST.md. The manifest grid carried a learning_rate axis
and no reg_lambda axis, following a misreading of the original's published
"2.0" as a learning rate. A parity review on 2026-08-19 established that 2.0
is reg_lambda; restoring that axis was required for protocol parity with the
original.

Executed binary grid (108 configurations; study_b/r6_parity_fixes.py GRID_BIN;
selection on val, finals refit on train+val per the original's protocol):
n_estimators {210, 420, 840} x max_depth {4, 8, 12} x reg_lambda
{1.0, 2.0, 4.0} x scale_pos_weight {1.0, 2.5, 5.0, 7.5}; learning_rate at the
library default.

Executed six-way grid (27 configurations; GRID_SIX, centered on the original's
published 500/7/1.0): n_estimators {250, 500, 1000} x max_depth {5, 7, 9} x
reg_lambda {0.5, 1.0, 2.0}.

Selected configurations are in artifacts/r6/variant_results_parity.json and
artifacts/r6/parity_fixes.json. The change was made for parity, not for
outcomes: the faithful headline (0.9803) and the superseded train-only
manifest-grid headline (0.9725) support the same conclusions, and
METHODOLOGY.md reports both.

## Format-sensitivity exclusion rule (filed 2026-09-28, before the train+val probe was scored)

Scorer input. Human posts are scored as extracted and normalized
(study_b/freeze_corpus.py). The extracted text keeps the page title for
about 22% of human posts (506 of 2,250) and carries no markdown. Generated
posts are scored as produced: every one opens with a title line and most
carry markdown headings or bold. A probe on the test split
(study_b/r8_title_probe.py, run 2026-09-25) rescored posts with only the
format changed and found features whose answers follow the format rather
than the post, above all PUR_OUT_003 and AUD_PRB_002, which answer "title"
when a title line is present.

Decision. Features sensitive to this format difference are excluded at
analysis time, as a format-sensitivity exclusion next to the outcome-blind
reliability filter. The instrument, scorer, prompts and all stored answers
stay frozen; nothing is rescored. The exclusion set comes from the rule
below, applied to a new train+val probe whose answers do not exist at the
time of filing.

Arms (study_b/r8_title_probe.py build):

- A1: AI posts through study_b/normalize.py normalize(): markdown stripped,
  title kept as a plain first line.
- A2: the same posts with that first line removed.
- H1: human posts whose scored text has no title (first line does not match
  the stored title), with the stored title prepended as a plain first line.
  Titles are cut at the first " | " and must have 3 or more words.

Sample (build --split trainval): train+val docs only (artifacts/r6/splits.json).
random.Random(202616) draws 50 AI posts per model, models in the order gpt,
claude, gemini, deepseek, kimi, each pool sorted by doc_id; then 250 human
posts from the eligible H1 pool sorted by doc_id. Scoring: the frozen
stage-5 scorer (study_b/r5_apply.py), all 11 dimensions per text, spend cap
$60.

Rule (screen --split trainval), applied to all 214 surviving features,
structural and style:

- For each feature and arm: total variation distance (TVD) between the
  feature's answer distribution in the original scoring
  (answers_full) and in the arm, over the arm's fully scored posts (at least
  95% of the post's original answers returned).
- Noise baseline per feature: noise95 is the 95th percentile (38th of 40
  sorted values) of the same TVD between the full run and a repeat run,
  over 40 draws of 250 full-vs-repeat answer pairs without replacement,
  random.Random(0), from the five repeat runs restricted to train+val docs
  (270 pairs).
- A feature is format-sensitive if its TVD exceeds 2 x noise95 + 0.05 in
  any of A1, A2, H1.

Use. The set flagged on the train+val probe is the exclusion set, removed
from every variant (structural, style, all features) before any v3
classifier is fitted. The test-split probe is confirmation only: its screen
is run with the same rule and reported with its agreement, and it never
changes the set. All feature-based analyses are then recomputed over the
remaining features with the unchanged protocol (val-selected grids, train+val
finals, bootstrap CIs, SHAP core selection). Baselines that do not use the
instrument (ModernBERT, stylometric, TF-IDF, length, Binoculars-style) are
unaffected.
