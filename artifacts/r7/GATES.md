# Rewording-durability verification gates (paper Sections 4.8, 5.4, Appendix J)

Gate record for the rewording attack: every AI post in the test split (1,450
posts = 290 prompts x 5 models) rewritten span by span by the model that
generated it, under the prompt in prompts/lamp_rewrite.md (iteration log in
its header). All gates were fixed before generation. Aggregate numbers are in
artifacts/r7/durability_aggregates.json; the scripts that produced and
checked the rewrites are in code/ (r7_lamp_rewrite.py, r7_verify_rewrites.py,
r7_claim_census.py, r7_rescore.py, r7_durability_eval.py).

## Pilot (before the full run)

2 posts per model (10 total), final prompt v3 plus a system message and an
in-loop trivial-copy retry guard: 0 length violations (ratios 0.824-0.996),
0 trivial-copy flags, 0 refusals, claim preservation 8/10 - the two misses
are borderline single-item edits (a timeframe word added; one list item
dropped), which set the expectation for the strict judge on the full run.

## Completion

1,450/1,450 rewrites (290 per model), 0 generation failures outstanding.
8 of 1,450 first-pass outputs were defective and regenerated before any
gate was scored: 3 truncated (reasoning tokens exhausted the output cap),
1 summary-length output, 4 over-condensed below the length bound. In-loop
guards (terminal-punctuation and length-ratio checks) were added to the
runner so such outputs are retried instead of surfacing post hoc.
deepseek-v3.2 no-ops the edit nondeterministically; in-loop retries plus
fresh-process reruns cleared its trivial-copy flags completely
(21 -> 7 -> 2 -> 1 -> 0).

## Mechanical gates (final files, all 1,450 pairs)

| Gate | Bound | Result |
|---|---|---|
| Length drift (rewritten/original word ratio) | [0.6, 1.4], fixed before generation | PASS - 0 violations (mean 0.922, median 0.965, min 0.607, max 1.057) |
| Trivial copy (>90% of 13-grams surviving) | 0 flags | PASS - 0 flagged |
| Refusal / emptiness / truncation | 0 flags | PASS - 0 flagged |

## Claim-preservation census and QC loop

An initial seeded 50-pair gate proved too noisy at n=50 (readings of 0.88
and 0.92 on near-identical samples; the judge is nondeterministic), so the
claim check was run as a census of all 1,450 pairs (same judge, prompt, and
parsing as the sampled gate), followed by a QC loop that regenerated every
"no" doc (max 2 regeneration attempts) and re-judged it.

| Census pass | Yes | No | Rate | "No" by model |
|---|---|---|---|---|
| 1 (pre-QC) | 1,310 | 140 | 0.9034 | gemini 93, kimi 22, claude 14, deepseek 10, gpt 1 |
| 2 (after regen attempt 1: all 140) | 1,398 | 52 | 0.9641 | gemini 38, claude 5, kimi 5, deepseek 3, gpt 1 |
| 3 (after regen attempt 2: the 52) | 1,424 | 26 | 0.9821 | gemini 21, deepseek 2, kimi 2, claude 1, gpt 0 |

192 regenerations covering 140 unique docs. Final census 0.9821 (the
paper's 98.2%), with 26 residual "no" docs left in under the 2-attempt cap.
The judge notes show the same single-item specificity-drop pattern
throughout (a dropped number, name, or list item; no wholesale meaning
changes). gemini is the outlier because it rewrites most aggressively
(0.003 mean surviving 13-gram share); dropping a specific under paraphrase
pressure appears to be a stable behavior of that model rather than noise a
third attempt would fix.

Residual doc ids (by rewriting model) - gemini (21): 0fe700a303a99e4a,
156b3c7885679f12, 1b7a15305c0c5f80, 27e374675bd9b961, 29ea121d1cf0dbd9,
30fcf8a1b57c116a, 378a48e4933a161a, 5b1c4ce1f2930072, 7cc38748752a46be,
969e8a543ece4d70, a2c7abe8812046cc, adca236fd49c7e29, b632bf06d491807d,
d0600dc7796bd6ae, d28f11fec7a4e8cd, d4f0551f2eff8150, d5dc5a11067e3424,
d6f4f351900514f6, dd218d111602480d, f6063b676eb450a8, f6a7b72623685781;
deepseek (2): 46489cd7918f8e66, 584d84cbe9401418; kimi (2):
80e98c06d3d96104, 969e8a543ece4d70; claude (1): 0e248ce80d75edfc.

## Rescoring gates (frozen stage-5 instrument on the rewritten posts)

Scoring reuses the stage-5 applier verbatim (same prompt template, feature
blocks, model, minimal thinking, aspect-based application, single-select
forcing - byte-identical by construction, since the rescore runner imports
the stage-5 code); only the input texts differ.

| Gate | Result |
|---|---|
| Full matrix | PASS - 15,950/15,950 answers (1,450 docs x 11 dimensions), 0 unresolved errors; 9 of 385,700 feature cells NaN-filled (0.002%) vs 4 in the original scoring of the same pairs |
| Off-option rates | PASS - mean 0.082% vs the original run's 0.089% on the same pairs; 3 features over 2% in both runs, and they are the same 3 features (a property of those features' option lists, not of the run) |
| 20-doc spot comparison | PASS - every sampled doc fully scored on-instrument; per-doc agreement with the pre-rewrite answers mean 0.844 (min 0.797, max 0.910) - agreement below 1.0 is expected, the rewrite changed the text |

Encoding: 1,450 rows x the frozen 868-column layout, asserted equal
(ordered) to the committed matrix layout; matrix sha256 prefix
554dceeeebe3fdff.

## Evaluation parity gates

Before any durability number was computed, each frozen classifier was
required to reproduce its recorded macro-F1 on the untouched original test
split: structural 0.9803, style-only 0.8811, all-features 0.9812 - all
PASS (recorded in durability_aggregates.json under parity_assertions).
