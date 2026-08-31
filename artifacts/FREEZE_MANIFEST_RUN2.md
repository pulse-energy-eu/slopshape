# FREEZE_MANIFEST_RUN2 (filled 2026-08-16)

Committed before any full-corpus classification number is computed.

| Item | Value |
|---|---|
| Instrument | 214 features (266 deduped minus 52 outcome-blind exclusions) |
| Taxonomy hash | 98ae4bd1624020ad |
| Exclusions hash | d02c4230f13d3acb |
| Style boundary | R4 strict rule (writing_style dim OR majority-high); hash 81d465ae19698060 |
| Encoder | one-hot nominal/binary, multi-hot multi_select, ordinal position, NaN missing (D9) |
| Encoded matrix hash | 05f43e8cc49e9917 |
| Splits | domain-disjoint (0.726, 0.138, 0.136), seed 202616, discovery pool excluded; hash 8e078336320a9bba |
| Doc counts | {'train': 1566, 'test': 290, 'val': 294} |
| Task | HEADLINE: binary human-vs-AI, narrative_strict variant, macro-F1 + AUPRC; secondary 6-way (macro-F1 + accuracy) |
| Grid (val-selected) | {"n_estimators": [210, 420, 840], "max_depth": [4, 8, 12], "learning_rate": [0.05, 0.1, 0.2], "scale_pos_weight": [1.0, 2.5, 5.0, 7.5]} |
| Variants | narrative_strict 187, style_only 27, all_features 214, core-only + core+FP per SHAP-bootstrap B=50 (paper section D thresholds) |
| CIs | 10k bootstrap, prompt-level AND domain-cluster (cluster primary), seed 202616 |
| Analysis list | SPEC 3.7 items 1-18 |
