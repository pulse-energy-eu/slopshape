# The 214-feature instrument

The frozen measurement instrument of the study, in reviewable form: every
feature with its definition, question, answer menu, and detection method, plus
every exclusion record from candidate to frozen instrument.

## Derivation chain

457 candidates -> 282 screened -> 266 deduped -> 214 frozen (187 narrative-strict + 27 style)

| Step | File | Count |
|---|---|---|
| Union of 3 discovery runs (11 B2B dimensions) | taxonomy_union.json | 457 candidates |
| Answerability screen | taxonomy_screened.json | 282 (38.3% rejected) |
| Screen rejection log with per-feature reasons | taxonomy_screened.screen_log.jsonl | one line per candidate |
| Embedding dedup, single-linkage 0.85 (F2LLM-4B) | condensed_taxonomy_0.85.json | 266 features |
| Style-audit boundary: 34 features excluded from the narrative-strict variant (all in writing_style) | style_excluded_features.json | 34 ids |
| Outcome-blind instrument floor: 52 features excluded with reasons (11 degenerate, 3 off-menu-prone, 38 unstable) | feature_exclusions.json | 52 records |
| Frozen instrument = 266 minus the 52 floor exclusions | (derived) | 214 features |

The style-audit exclusions define the narrative-strict variant boundary, not a
removal from the instrument: the 27 surviving style features form the
style-only variant. Per-feature answer distributions, off-menu rates, and
stability values are in artifacts/r5_gate/feature_sanity_report.json; the
3-run style-audit ratings are in artifacts/r5_gate/ratings_v2.jsonl.

## Hash verification against the freeze manifest

artifacts/FREEZE_MANIFEST_RUN2.md records first-16-hex-char sha256 hashes,
committed before any classifier was trained. Check them against this package:

```
python3 -c "import hashlib; print(hashlib.sha256(open('condensed_taxonomy_0.85.json','rb').read()).hexdigest()[:16])"
```

| Manifest item | Expected | File here |
|---|---|---|
| Taxonomy hash | 98ae4bd1624020ad | condensed_taxonomy_0.85.json |
| Exclusions hash | d02c4230f13d3acb | feature_exclusions.json |
| Style boundary hash | 81d465ae19698060 | style_excluded_features.json |
| Splits hash | 8e078336320a9bba | ../artifacts/r6/splits.json |

The fifth manifest hash (encoded matrix, 05f43e8cc49e9917) is over the
per-document feature matrix, which is gated; rebuilding it from the fetch
pipeline plus stage-5 application reproduces it.
