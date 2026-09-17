# Filed decision records

Two decisions were written down with a date before the data they govern
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
