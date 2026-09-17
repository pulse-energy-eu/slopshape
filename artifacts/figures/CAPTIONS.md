# Final figure captions (S8 draft input)

**f1_pipeline**: Study pipeline. Top row: corpus construction and measurement (human corpus, brief-mirrored AI counterparts, template extraction, feature discovery with answerability screen and dedup, LLM scoring). Bottom row: outcome-blind instrument floor, encoding with domain-disjoint splits, classification, the rewording test, and the validation checks.

**f2_rarity_violin**: Structural rarity percentile by source (k=25 nearest neighbors in the z-scored narrative-strict feature space, train+val reference; bars mark source means). Humans concentrate in the rarest regions (mean 0.84 vs pooled AI 0.44; Cohen's d = 1.83; original: 0.71 vs 0.49, d = 0.83).

**f3_variants**: Binary detection macro-F1 on the held-out domain-disjoint test split, by feature variant (bars; final models retrained on train+val per the original's protocol; error bar = 10k domain-cluster bootstrap CI on the headline). Diamonds mark the original study's corresponding fiction-domain results. Ordering combined > structural > style replicates; every variant lands above its original analogue. Y-axis starts at 0.80.

**f4_shap_top20**: Top-20 features of the structural (narrative-strict) classifier by bootstrap-mean absolute SHAP contribution, labeled with their plain-language instrument names (feature IDs in parentheses; full question wording in the released instrument). Dark bars mark the ten core features (Section 6).

**f5_confusion6**: Row-normalized test confusion of the six-way source-attribution model (macro-F1 0.792 vs 16.7% chance). Humans are near-perfectly separated; the residual confusion is AI-vs-AI, hardest for DeepSeek V3.2.

**f6_lda**: Two-component LDA projection of the encoded structural feature space (12,900 documents). Human posts (blue) separate along LD1; the five AI models overlap heavily with each other, consistent with the original's geometry finding (human dispersion 1.42x AI).

**f7_lengths**: Word-count distributions by source (boxes = IQR, whiskers to 1.5 IQR, outliers hidden). Mirrors run longer than their human sources (disclosed as R3); the length-matched sensitivity (8.4) and the failing length-only baseline (6.1b) bound this confound.
