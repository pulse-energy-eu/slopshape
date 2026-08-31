# Deviation register D1-D16 (paper Table 2 / Table E1 source)

Every deviation from the original study (Russell et al. 2026, arXiv
2604.03136; its methodology is vendored in the repository) is declared here.
The paper's condensed Table 2 and full Table E1 are generated from it.

| # | Deviation | Defense |
|---|---|---|
| D1 | Domain: B2B posts | the research question |
| D2 | Brief extractor gemini-3-flash (their 2.5 deprecated) | declared |
| D3 | Brief prompt adapted + anti-quotation clause | Publisher-blind by design |
| D4 | Dedup threshold = the original's 0.85 RETAINED (not silhouette-selected); sweep 0.70-0.95 published with monotone silhouette disclosed (battery 8.12) | our merge 5.7% vs their 25.5% at 0.85 = corpus-density difference |
| D5 | Style audit 3 runs + agreement (theirs 1) | exceeds |
| D6 | Domain-disjoint splits + single-unblinding holdout (theirs random prompt split) | stricter |
| D7 | Rarity re-implemented from text | verified on their data; magnitudes disclaimed |
| D8 | Stages 2/3 via OpenAI direct | provider plumbing |
| D9 | Encoder fixes (ordinal by taxonomy position; nominal one-hot) | released code deviated from their own paper |
| D10 | Corpus scale 2,250 prompts (~1/4.5 of theirs) | budget + domain scarcity of pre-2022 archived posts; power note: prompt-bootstrap CI half-width ~1.4 F1 at this scale is adequate for the headline; per-class 6-way and top-1% tails underpowered vs theirs, stated in limitations. Discovery pool = 4.4% of corpus vs their ~1%. |
| D11 | B2B-native template schema discovered from human posts (theirs: NarraBench fiction schema) | fiction lens misfits commercial posts; mechanism unchanged; mapping table published (artifacts/TEMPLATE_SCHEMA_V2.md) |
| D12 | Mirror max_tokens 8,000 (theirs 128k/65k) | matched to B2B target lengths |
| D13 | Evaluation-stage models upgraded within family lineage (GPT-5.x: luna/terra; Gemini Flash: 3.6); generators unchanged | rule: same-variant newer versions for non-generating tasks; quality-cost frontier documented; pilot gates |
| D14 | Rewording test: each of the five generator models rewrites its own posts, all 1,450 test mirrors (theirs: 278 posts, one model as rewriter) | realistic production pattern (a publisher polishing a draft uses the model it already works with); removes the original's single-model asymmetry; yields a per-model durability breakdown |
| D15 | Rewording prompt is instruction-only (the original's 25 few-shot professional examples are fiction rewrites) | domain adaptation, declared - not parity (prompts/lamp_rewrite.md) |
| D16 | Content-preservation constraint added (keep claims, facts, links) | verified by a full claim-preservation census over all 1,450 pairs (artifacts/r7/GATES.md) |

Inherited without re-test (declared in the paper): classifier family choice
(XGBoost over linear/RF), stage-3 batching-model choice, stage-5
minimal-thinking choice - the original's evidence is cited; re-tests would not
change the design.
