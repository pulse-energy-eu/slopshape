# Manifest

Complete inventory of the release package. One line per file: purpose, size
in bytes, sha256. Verify any file with `shasum -a 256 <file>`. The
first-16-hex-character prefixes of the instrument and splits hashes are
exactly the values committed in artifacts/FREEZE_MANIFEST_RUN2.md before any
classifier was trained.

## Top level

| File | Purpose | Bytes | sha256 |
|---|---|---|---|
| README.md | Package front door: study summary, contents, verification and rebuild guides | 7950 | c1703f0940e8a84de0b5a734d9a8cb3da68c0d78f8ee05e09b6bf9fb312449cb |
| VERIFICATION.md | Number-by-number map from every paper exhibit to artifact and regeneration script | 13340 | 0afc6feedcd1cb76f9003af92a792a5d2a92b539a9b41bc43dbfb5b8fa16fee1 |
| MANIFEST.md | This file | - | (excluded from its own checksum) |
| LICENSE | PolyForm Noncommercial 1.0.0 for the code directories; all rights reserved for the rest | 5846 | d1d49d7c98867408981dab0308f1d4b9be847c5c6bddbb2a0ebba314783abcbb |
| setup.sh | Environment bootstrap: pinned venv, pinned upstream clone (vendor/storyscope) + fork patch, drift check | 3540 | df618915f1f687b4a60a9a5dcee4b2ea0149c757377f1e932975831f9b36af27 |
| requirements.txt | Pinned Python dependencies (the versions that produced the paper's numbers) | 728 | 3b3109db1f40d82f60485405d133282f3d6e3276c51b13a224c31d61249c3d60 |
| env.example | API-key names (values never committed; keys only needed for the LLM stages) | 718 | 821b77097df6ca7bee912e2edbb6f2be87d2bc3f9d799da120f49bbbb0cc02b4 |
| .gitignore | Excludes the local venv, vendored clones, data, outputs, and .env | 48 | cc3d92eba785a0a6c569df4b0050e92b8ef523fab77618ea696501b2d58f4f8a |

## artifacts/ - canonical records

| File | Purpose | Bytes | sha256 |
|---|---|---|---|
| METHODOLOGY.md | Canonical methodology + results record; every paper number appears here in context | 34659 | 9a126c3258aaacd7090e2702bd38022b625bb2c173a9ff9372e4902961e85d34 |
| FREEZE_MANIFEST_RUN2.md | Pre-training freeze: instrument hash chain, seeds, splits, grid, analysis list | 1256 | 7f48169fb623f5e68ac3356f8e55b8e1e3b64b1cd35c04db84f41d0c05b7c516 |
| TEMPLATE_SCHEMA_V2.md | Frozen 11-dimension B2B template schema with the NarraBench mapping table (paper Table B1) | 31157 | 391db3f346b4a69da4cbe883a64e835a8c97e0854189a22f12308eb0aabe2bcd |
| DEVIATION_REGISTER.md | Deviations D1-D16 vs the original study (paper Table 2 / E1 source) | 2988 | 0752c2c039396c3ee22015e21724d3f48e614cd21e3cc7bc8a2267cc211ba031 |
| REPLICATION_CONTRACT.md | Line-cited contract against the original paper, incl. the released-code defects we fixed (paper Appendix I source) | 8105 | a949b87d3e6bd9d5795374fefd32ab50dc9d7cc60c381aaf0fbb4c5640804a88 |
| our-fork.patch | Exact diff of our fork against the original's released pipeline | 17592 | 38d498b1cbc610497c6b8e9e833b7649db2e114c61e8150517990d904d6b5a70 |

## artifacts/r6/ - aggregate result artifacts (canonical set)

| File | Purpose | Bytes | sha256 |
|---|---|---|---|
| PAPER_TABLES.md | Generated paper tables T6 and T13-T16 (paper Tables C1, 6, and F3) | 3779 | 8972a8230a6d96854071e7cb044b0a34d6b7d48b271ac9e68c7a464db5ea2990 |
| variant_results_parity.json | Faithful-protocol headline variants: narrative-strict 0.9803 (both CIs), style, all-features | 1199 | cda88aab7db4a1d6c37e2c94ebe5fe4bd0a4344c4d2533a2064bcdb01e5dc760 |
| core_values_selection.json | Value-granularity core selection: 10 core values, signed directions, core-only 0.9348 and core+fp 0.9593, core attribution share 0.2759 (the paper's 27.6%) | 2220 | 1d99eadfc5e4230bf124191228f1624269538ca0b19e80c0123e0fd033f5cd77 |
| parity_fixes.json | Parity batch: direction-hypothesis delta + TOST, core/fingerprint pass with six-way config, per-class F1 (paper Table 5) and fingerprint id lists (Table F3), rarity AUC, length tertiles | 1993 | 19ffff9536f90da515e5c1764cfcc3ae6e2053334ff194e662c4e9e0416baf49 |
| s9_fixes.json | S9 reruns: direction-hypothesis package (cluster CI, McNemar), untuned-constants sensitivity, TF-IDF/stylometric/length baseline finals, exact memorization rules, faithful length matching | 2439 | 81f5d529a8e3bff4b9abc9dd1e6815712ab42cc562301845add3fe3d3ae4129e |
| review2_fixes.json | Faithful battery reruns: entity/YC/era/format/pool/split-seed, error overlap, learning curve, six-way, geometry extras, pairwise kappa | 1729 | 0ae8037555686919402e4cc4c2d26a836ec53b5589277932652bd7b5bcaf8547 |
| review_batch.json | Format-mismatch audit, pool-domain overlap, geometry, mirror length adherence | 3343 | 0005e3d4b13d53fe754f7a184c349517a6a38fdc3a2c88381cdfbbc6edf2ad0c |
| vertical_rarity_faithful.json | Faithful vertical Kruskal-Wallis + per-vertical F1 + rarity tail composition on both bases (paper Table F2) | 3341 | 25a4d274cc6560c4def3390c2b8c68922c2a3fc2754a3c5a6375353a7f74d561 |
| rarity_report.json | Rarity statistics, train+val and all-corpus references (paper Table 7) | 758 | 3409eb0e5e87445359a17a0ba71fe63e48442c4c7d1f3a0f417d33d791439a95 |
| baselines.json | Raw-text baselines incl. ModernBERT and the Binoculars-style substitute (stylometric/TF-IDF/length train+val finals in s9_fixes.json) | 921 | fff96a0e67dfa747fd734700fb1dcca59a7d2df14f922194244c92be2adb41c5 |
| writeups_811_812.json | Template-vs-direct ablation and dedup-threshold sweep (batteries 8.11/8.12) | 2131 | 1cf38e64e4059bca84482256e466d35c5beaf101d965abe24800eacf04377787 |
| template_vs_direct.json | Raw candidate counts behind the 8.11 ablation | 240 | ec5535062b435a5ace89348f2bcd934e0a2cb1e3c7127f2ffdd3c980c3f89bd4 |
| splits.json | Frozen domain-disjoint splits (seed 202616); prefix = freeze-manifest splits hash | 78303 | 8e078336320a9bbaeadf9ad72b13bb6a0903979c08ede5482c46e585bba0573b |
| variant_sets.json | Feature id membership of each classifier variant (187/27/214) | 8208 | 6e65b0a480bfeeb53e2bf03bc27aa72996c66c6ff92f31a39ad72f4ea9a7c3d6 |

## artifacts/r7/ - rewording durability (paper Sections 4.8, 5.4, Appendix J)

| File | Purpose | Bytes | sha256 |
|---|---|---|---|
| durability_aggregates.json | Aggregate durability results (paper Table 4): parity assertions, unattacked/attacked macro-F1 + AUPRC for the three feature classifiers, attacked structural CIs, flip counts, per-model attacked structural F1, attack magnitude, gate outcomes, rescore coverage | 6303 | eaebc1a924e74e4c9da0f57453a152d25e0cc6d16b22178e6b2d0826aef57847 |
| GATES.md | Verification-gate record: pilot, mechanical gates, claim-preservation census history with the QC loop and residual list, rescoring gates, evaluation parity gates | 5342 | 89773ed319c3d18e63a9350bd627bd8c20e151fc92a2df8203aaabcc13ce5b7f |

## artifacts/gold/ - human gold session

| File | Purpose | Bytes | sha256 |
|---|---|---|---|
| GOLD_RESULTS.json | Gold-session scoring (corrected final): kappas, unclear flags, style-boundary audit (paper Table 9) | 1123 | bca073f0359ddb817fcb192370251e14cf9e6ddf387bf0fcb098c881d536bdb3 |
| DRAW_1_MANIFEST.json | Pre-annotation committed draw: seed, doc ids, features, protocol | 8447 | 3a2abae2863bfd80d838b55497e884632846a76da8be1692695ee1a7552c13c5 |
| style_audit_sample.json | Seeded 40-feature sample for the human style-boundary check | 4203 | 6c022a1db514f6037aef95212998dab1a440edc7e2c497109d5c3af34d261160 |

## artifacts/r5_gate/ - instrument QA records

| File | Purpose | Bytes | sha256 |
|---|---|---|---|
| style_audit_summary.json | 3-run style audit: agreement 0.989, 34 exclusions | 398 | 533a690978b499de9b8971022fbef0204181ff9b1bea0583dc91ec69d570a7d7 |
| ratings_v2.jsonl | All 266 x 3 style-dependence ratings | 237715 | c681461ce6104c4e881ec94a57f7bd7ef4402456770b08f58f1d473e8620de17 |
| feature_sanity_report.json | Per-feature answer distributions, off-menu rates, stability (floor evidence) | 9765 | 918733e1264e9c5146cb9312edf084f2ae9542bff5eb7f69afbc481790a571d0 |
| repeatability_report.json | 5-run repeatability: alpha 0.8907 vs gate 0.8 | 113 | f79af9c33d50146cfe8715c6c2a8287d690baf104d185d994efe4d56a7f56b54 |
| coverage_report.json | Aspect-vs-single-call coverage check (paper Appendix C) | 128 | b95f9b957e2e5362c11225ba024a277d6e6b2c9231d16e80486d8e98a323ac3b |
| MINIVALIDATION_VERDICTS.json | PI mini-validation gate verdicts: 39 OK / 1 AMBIGUOUS / 0 WRONG | 638 | aa75cb21a97d179da5b63b53942ca70d0e9bd02de5ba9eca92fdb4aad83fdeaf |
| pack.json | Mini-validation sample definition (seed, features, doc ids) and extractor answers | 16477 | 2bb27a3108269a277fd7adddf2625f211248b86eda57d58f94aba4d88f6fbcea |
| VERIFICATION.json | R5 full-matrix completeness check (148,500/148,500) | 130 | d6cc4e8a1bd8b904b891a6ec38dac74bc8a014fd15560fa901e879534290ac91 |

## artifacts/figures/ - rendered paper figures

All generated by study_b/r6_figures_final.py; captions in CAPTIONS.md
(2237 bytes, sha256 bda9448e4179b6e05853f9e15b8f53afa42a6fc6474f1e455bedcaae7d2c39cb).

| File | Paper figure | Bytes | sha256 |
|---|---|---|---|
| f1_pipeline.png | Figure 1a pipeline schematic | 163666 | 16705320d3e41ff917af47d039098be9b687ef292ecbf98e46d340d7fa7e91c2 |
| f2_rarity_violin.png | Figure 1b rarity violins | 232972 | c206505851e924b725c446fda827987044bb9af8fbf884fcf2c9fd13aab23543 |
| f5_confusion6.png | Figure 2 six-way confusion | 152454 | 07a1fdbc83fdf38cdef5ac6d57b0c9eeabb52c3cc1516aeeb01f0accd26d7db9 |
| f4_shap_top20.png | Figure 3 top-20 SHAP | 403811 | d2697448bbffb51ae5d5554406173d675847519175344f697557cfcbb1413aab |
| f7_lengths.png | Figure A1 length boxplots | 76828 | a3fafa1e71c30a635bbdee735519a933f60d9b8c90a49aafcae56ebd2f440a1c |
| f6_lda.png | Figure F2 LDA projection | 838277 | e009b9d9a14efd940f51bed032d872a2149ed5ef5a39108ce852aad8a5b9ae04 |
| f3_variants.png | Variant bars (supplementary) | 161166 | 6638952d6ec7e87c6197ef8e43314b1105d4202fd5c65a5f4d34dd91e7abb9e9 |

## instrument/ - the 214-feature instrument (see instrument/README.md)

| File | Purpose | Bytes | sha256 |
|---|---|---|---|
| README.md | Derivation chain 457 -> 282 -> 266 -> 214 and hash verification guide | 2376 | aa448c265219929f0af6fa6cd735f954d674b8d74ebe0583d83c4149983bfd1b |
| taxonomy_union.json | 457 candidate features from 3 discovery runs | 331462 | f86910d0d7afb3d80a4389c604ff202113864be6745edf0bd5f09eb6524160a0 |
| taxonomy_screened.json | 282 features surviving the answerability screen | 200526 | 114f7ac8e40057b8a5bd5f0871ac936a5df138f08aa643fdd67330169698921d |
| taxonomy_screened.screen_log.jsonl | Per-candidate screen verdicts with rejection reasons | 172985 | 44c5c00178ddf95849e6e07b067564e96391b70f7f378587b5d90b648b602061 |
| taxonomy_screened.screen_summary.json | Screen totals: 282 kept / 175 rejected (38.3%) | 85 | 8fce089ac25c36db42246d7fc3b89433c65e81e612ac7f96f70ae28919f1d84e |
| condensed_taxonomy_0.85.json | The deduped 266-feature taxonomy: definitions, questions, answer menus, detection methods; prefix = freeze-manifest taxonomy hash | 188498 | 98ae4bd1624020addb36da126ea691a4fe23f3e94a1d6d6f72ea3638b83cd01d |
| style_excluded_features.json | 34 style-boundary exclusions (narrative-strict variant definition); prefix = freeze-manifest boundary hash | 580 | 81d465ae19698060d9afabdbc9b32273fba82e78b0026508f828c767c13e55ca |
| feature_exclusions.json | 52 outcome-blind instrument-floor exclusions with reasons; prefix = freeze-manifest exclusions hash | 6037 | d02c4230f13d3acbba08235b0bbc1a9edd3b9edde367fe53448c1d34e73cd7f9 |

## prompts/ - complete prompt set (see prompts/README.md)

| File | Purpose | Bytes | sha256 |
|---|---|---|---|
| README.md | Map of every prompt: files here plus script-embedded prompts | 3884 | c4508793b108ec0ba9063c4abbab49892f24b11af1cfa407e4ddd9112bfd4713 |
| stage5_feature_application.md | Stage-5 scoring prompt (verbatim copy; source of truth is the PROMPT constant in study_b/r5_apply.py) | 2109 | 04c8fae2d7401c9b7bde38f7b5a1c91431cb56e8b7f9f390aacfeded6614cf1a |
| cross_source_comparison_b2b.md | Stage-3 comparison prompt | 2569 | 4509c2bf67a5ee0e326fb191e37c2221664b139e72becc109ff3411ac95887fc |
| aspect_b2b_purpose.md | Stage-4 feature-discovery prompt, purpose dimension (dimension-expert discovery, 3 runs) | 6839 | e251fb7615f64c32918088d227f02163acff674dab8dae5c62a76bd40e55b957 |
| aspect_b2b_audience.md | Stage-4 feature-discovery prompt, audience dimension (dimension-expert discovery, 3 runs) | 6908 | fce51c56aec52c0311db51df59860192143bd2f0b7266ef1a5e9722874b348e2 |
| aspect_b2b_structure.md | Stage-4 feature-discovery prompt, structure and flow dimension (dimension-expert discovery, 3 runs) | 6877 | 5932ea5b3039c82853a0cd940d23d8b4cf009fb7aef892c56939d034680d013e |
| aspect_b2b_explanation.md | Stage-4 feature-discovery prompt, explanation dimension (dimension-expert discovery, 3 runs) | 6853 | 521edb4c37a58d471bed28f030043b32e9f6ae16afce35d2ba42883e50aed0b5 |
| aspect_b2b_evidence.md | Stage-4 feature-discovery prompt, evidence dimension (dimension-expert discovery, 3 runs) | 6907 | 8b0004b0d0af9584fa552b1629d9076c210b6c8bfee10a1b363e90d074116ed4 |
| aspect_b2b_voices.md | Stage-4 feature-discovery prompt, voices dimension (dimension-expert discovery, 3 runs) | 6989 | a10cf30dee200245e857dd8e35a860fa0584233cd18665cdf9a8525035f81fa3 |
| aspect_b2b_actionability.md | Stage-4 feature-discovery prompt, actionability dimension (dimension-expert discovery, 3 runs) | 6579 | ad1109ea9807a1d022df2ba66c43a935205a08140c02b55bbbff93a0cf5d9a1b |
| aspect_b2b_commercial.md | Stage-4 feature-discovery prompt, commercial integration dimension (dimension-expert discovery, 3 runs) | 6946 | 94783f44a73669769ac5cbcdf270b94910ee97b0d7653bedf3175f459a23f581 |
| aspect_b2b_timeliness.md | Stage-4 feature-discovery prompt, timeliness dimension (dimension-expert discovery, 3 runs) | 6639 | 2a22f5c5b3ddedede61c8240eefd12979239ff85571c05b1f87974a4a1c182ff |
| aspect_b2b_pageformat.md | Stage-4 feature-discovery prompt, page format dimension (dimension-expert discovery, 3 runs) | 6912 | 0dd64e42ccbacff9b70fe691b360ae6b64b76fbce0c74d420b62048946f53d51 |
| aspect_b2b_style.md | Stage-4 feature-discovery prompt, writing style dimension (dimension-expert discovery, 3 runs) | 6480 | 76cc64990fe41d74e552e2b43f7d4c6b1a3df11fdfda91aa60ce6a2ec2e41ef1 |
| lamp_rewrite.md | Stage-6 rewording-attack prompt (LAMP span-level self-rewrite), iteration log in the header | 5076 | 3221b9839c9b6ba2c41c08a5537c95b2e467f649bed6003027013dcab79c8641 |

## code/ - stage guide + durability scripts

| File | Purpose | Bytes | sha256 |
|---|---|---|---|
| README.md | Study stage -> repository entry point map, environment, spend, protocol note | 6140 | 269290aed011bb9fb6a9d2f88b89e69317c088b6eaea52d5b3f03ad8cd5ab8d3 |
| r7_lamp_rewrite.py | Rewording-attack harness: each generator model rewrites its own test mirrors (in-loop degenerate/copy/truncation/length guards, resume-safe, spend-capped) | 14497 | aa30f5f3595e1780bca27b93f1d0c49fe4af0cdbeb196c1a2bfbdd6f512b67ca |
| r7_verify_rewrites.py | Rewrite gates: length drift, trivial copy, refusals, seeded claim check | 10198 | aedd4938bd346bbcfb575368cae57fd7baf99babda2f59380dd00eb64816e5f9 |
| r7_claim_census.py | Claim-preservation census over all 1,450 pairs (judge reused verbatim from the gate script), resumable across QC passes | 5965 | 9d74337a70a6d8aff1bb27d9a3fbb95b8c4a2bd212ec2ef0d4c4dd4410ebe20e |
| r7_rescore.py | Rescoring runner: frozen stage-5 applier on the rewritten posts (imports the stage-5 code, so prompting is byte-identical) | 3579 | 0b14b410538542589b06ecf5dd6807e40f6af8fe8c58153945119b381097783a |
| r7_durability_eval.py | Durability evaluation: frozen structural/style/all-features classifiers on the reworded split, with parity assertions, flip counts, and bootstrap CIs | 9130 | 3d4a028f996721b8d05241fd11134bc53df232ab253ce5e2c11ccb85cfbdf8dc |

## study_b/ - the analysis pipeline

Every regeneration script named in VERIFICATION.md and code/README.md, plus
their imports. Scripts run as modules from the repository root
(`.venv/bin/python -m study_b.<name>`). The five r7_*.py durability scripts
are additionally copied verbatim into code/.

| File | Purpose | Bytes | sha256 |
|---|---|---|---|
| __init__.py | Package marker (scripts run as study_b modules) | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| answerability_screen.py | Instrument answerability screen (gpt-5.6-terra, strict 2-vote) with embedded prompt | 6839 | 6603c06c6d6edefe217e6d5c9ac7a5dd0f93dac436eecb2a367fb20683cae8a5 |
| build_composite_frame.py | Funnel step 1: composite frame assembly + deterministic anti-persona prefilter | 4246 | 1105bc168d3e66b98c9b9f37754806f246299fe6517ceef4480eb0c805404b3a |
| build_corpus.py | Funnel steps 5-6: quota selection + deep Wayback fetch through the content-filter chain (writes ledger.csv and the corpus parquet) | 15114 | cf0f3e0416b914bf9684385cb26aa552a84088fe1adccd14b7bacf89c663e6b6 |
| build_frames.py | Funnel step 1 source-frame construction (Inc5000/FT1000/G2) with Wayback resolution | 16936 | 858ab3bafbfddd1a12ea3cae01ab3fdeff4484fdc53b043475c28539c53c29d1 |
| compare_repeatability.py | 5-run repeatability scoring (Krippendorff alpha, pairwise kappa) against the pre-committed gates | 4167 | 5a53ed3ce17d7a55571591a5ba9b35d7cb3f0cf249a02e990fce3bafb148d9ed |
| derive_kept.py | Funnel steps 4-5 keep-eligible derivation from the spot-check decisions | 1339 | 6194e7a8317681755ab11117ffae79c2e429ed95c0629ef7bd0e8eb86f4d86ad |
| extract_briefs.py | Brief reverse-engineering from each human post (2-call design, anti-quotation clause) with embedded prompt | 10549 | cc709eac958ce157db463243f9e1a9146e7beec5aae904a7ec2516d19d9c130e |
| extract_templates.py | Stage-2 template extraction against the frozen schema (gate-selected model choice) with embedded prompt | 13263 | 99ff3f4a11fba397131aa26a1dc05b6306bfc49862bdaac06fefa218a147b18c |
| find_domains.py | Funnel step 3 Wayback CDX volume qualification over the screened frame | 20332 | b6fe630197324b622a4a7137899058de646ba298c4730dd55b27b5d183e9c43f |
| freeze_corpus.py | Corpus freeze: vertical normalization, frozen parquet, corpus manifest export | 1771 | 4665bf6e7a25e2cfe51b8c277863983ff8efb84945e37ff8f34e8240cf6bd81a |
| generate_mirrors.py | Mirror generation with the five generator models, with embedded generation instruction | 11341 | 9ba9cea53a6283991c643cdf6d1bc7dddcb75d924810255649fc6ca4387687cd |
| icp_screen.py | Funnel step 2 company-fit screen (gpt-5.6-luna, 2 votes) with embedded prompt | 6428 | 26c6556fa79dab58ffe70e6cfe8556da82987656f73324372307bd1269c1397e |
| noaq_briefs.py | Brief ablation variant without the anti-quotation clause | 1355 | f89eb8b5cbd3a412e6f0cf04408890a3e3847c469d6448bda5b81d3fa9d23161 |
| normalize.py | Text normalization shared by fetch and analysis stages | 7285 | cb9766422ca15d02a0e07ee2c22fcdb92b7aec55ebdf0acbecff3dea7ee5c146 |
| r3_dedup.py | Stage-4 dedup clustering (F2LLM-4B embeddings, threshold 0.85 + published sweep) | 2740 | bd1aa7d05b87ae5890eef33b76301bc4fde3885de0fd0fdab43bd040a6baba7e |
| r3_discover_b2b.py | Stage-4 discovery driver: injects the 11 B2B dimension-expert prompts into the vendored discovery stage | 1783 | 4da5ce22e6bca01069a40c455bdca3c6a5024a086a2b74a5ef42c4779249b3b3 |
| r3_discovery.sh | Stage-3/4 batch runner (resume-safe, spend gates, status files) | 8640 | 42e87d68c2279da642e9b5425c6a582d96223ed2506d8d2b45a76c9769f669f8 |
| r3_pipeline_input.py | Stage-3 pool selection and export (templates + raw ablation variant) | 4111 | e1e9365ff7e421a15684437a62fba7e04d7ae537e2ee43f8f039bb68f0ef5534 |
| r3_union.py | Stage-4 union taxonomy across the 3 discovery runs | 2859 | c888ff488446420639ba9ed8e41206e35aab5c747fa40731b92bf77a8f357f6e |
| r4_style_audit.py | Style-dependence audit (gpt-5.4, 3 runs, strict boundary) with embedded prompt | 7361 | d23c387a69d47c1722f201abac7898108765aff9f3d2aa7e9b7416c7bc40f9ed |
| r5_apply.py | Stage-5 feature application: the scoring harness and the PROMPT constant (source of truth for prompts/stage5_feature_application.md) | 9525 | 45c8ac6226e022d0e1e396425b9d371a969069340e88b94921925f3b382839b9 |
| r5_qa.py | Stage-5 QA gates: matrix completeness, off-option rates, canonicalization | 6146 | 490e9393d0b75fceeedb98f20db895f354f146a1184d0575c12262bc0ad1e6d5 |
| r6_baselines.py | Raw-text baselines: stylometric, TF-IDF, length-only, Binoculars-style substitute | 7941 | a4354a1f01674d400d721548579feee2b5d4236debc7538831c9358c3f051810 |
| r6_battery_tail.py | Batteries: temporal/era control, post-cutoff entity scan, YC sensitivity | 6377 | 9c5eb29fce6c96aead7e492e2242abdbcc4e7d5a6b65fb33eb8608fb5831ef3b |
| r6_build.py | Encoding + frozen splits + freeze-manifest generation (D9 encoder, seed 202616) | 7807 | dbc285d72537e3ef2397cf685f677a1f9247c12e03451b4540a95b7642648ff1 |
| r6_core_values.py | Value-granularity core selection + core-only/core+fp variants + core attribution share | 6005 | 0951432729cfe28b0d2cf74822a070ecb61ce51d03f8be694558a7b7b9ff9395 |
| r6_figures_final.py | All released figures (asserts the reported six-way 0.7917 on its internal refit) | 16792 | e53a7b193dd9c266965e69c430699b84fdd5c350f04ae9144616cd3fa590ef23 |
| r6_paper_tables.py | Generated paper tables T6/T13-T16 | 4915 | e7b6bd279798e0e121ddf2a6b5d5bd16f1e7a763340cde9d901c5e31ffc8b5da |
| r6_parity_fixes.py | Faithful-protocol training: grid, variants, SHAP, CIs, H1'/TOST, six-way per-class, fingerprints (asserts 0.9803 on refit) | 14738 | 8e8667324e28ab8b3edc194dbea1817cf972dafd703b4d44a4ce89505e43403d |
| r6_rarity.py | Rarity statistics on the frozen encoded matrix (train+val and all-corpus references) | 3202 | e434a3ee20349a9e8eefab349a5423016144630ac95635cb54ff6518dafa66ec |
| r6_review2_fixes.py | Faithful battery reruns: entity/YC/era/format/pool/split-seed, error overlap, learning curve, six-way, geometry | 14313 | 045e552a0350febf8d74f91c5756e6e9c8c6396d445f42979cc2fd2249799a52 |
| r6_review_batch.py | Format-mismatch audit, pool-domain overlap, geometry, mirror length adherence | 8095 | d5e929687a59e74c13ce4fe2b4cd087afb9f490f5629af397c04dee1bf225db5 |
| r6_s9_fixes.py | S9 reruns: direction-hypothesis package, untuned-constants sensitivity, baseline finals, exact memorization, length matching | 14640 | 2e5a6a57fc56f1352d96fbf93c13d748a8d78c42b37e1db6fe3d95cd6b3772b6 |
| r6_train.py | Shared training core: load, variant columns, fit, metrics, SHAP bootstrap output | 8930 | 449127288a3a2412c1a90f960c7e8eeac73b420c242df934bd00ad6985462d12 |
| r6_vertical_rarity.py | Faithful vertical heterogeneity + rarity tail composition | 5254 | 773a540e9c2c660033427cbfdb0dcbbdd313f55a311b419e67567bbebf233b5d |
| r6_writeups.py | Batteries 8.11/8.12: template-vs-direct ablation and dedup-threshold sweep | 5478 | fc3eb6f4a48e303f9efdc95e358c8477674b6f59f18bfa4a4ca59603bf61b490 |
| r7_claim_census.py | Claim-preservation census + QC loop (canonical; code/r7_claim_census.py is the verbatim copy) | 5965 | 9d74337a70a6d8aff1bb27d9a3fbb95b8c4a2bd212ec2ef0d4c4dd4410ebe20e |
| r7_durability_eval.py | Durability evaluation on the reworded split (canonical; code/r7_durability_eval.py is the verbatim copy) | 9130 | 3d4a028f996721b8d05241fd11134bc53df232ab253ce5e2c11ccb85cfbdf8dc |
| r7_encode_rewritten.py | Encodes the rescored rewritten answers with the frozen r6 encoder (column layout asserted equal) | 5547 | 9463648a2c93c0719b8982664c7d2fcd884a7112418c4cad2f1585ba40eec4f8 |
| r7_lamp_rewrite.py | Rewording-attack harness (canonical; code/r7_lamp_rewrite.py is the verbatim copy) | 14497 | aa30f5f3595e1780bca27b93f1d0c49fe4af0cdbeb196c1a2bfbdd6f512b67ca |
| r7_rescore.py | Rescoring runner for the rewritten posts (canonical; code/r7_rescore.py is the verbatim copy) | 3579 | 0b14b410538542589b06ecf5dd6807e40f6af8fe8c58153945119b381097783a |
| r7_rescore_qa.py | QA gates for the rewritten-post rescoring run (coverage, off-option, scorer sanity) | 7341 | 762fb3e5e604e5f6f69ba0daaf25d3438492ef48252892cc826821ea299e8aa8 |
| r7_verify_rewrites.py | Rewrite gates: length drift, trivial copy, refusals, claim check (canonical; code/r7_verify_rewrites.py is the verbatim copy) | 10198 | aedd4938bd346bbcfb575368cae57fd7baf99babda2f59380dd00eb64816e5f9 |
| rarity.py | Rarity metric implementation (verified against the original's data) | 6503 | 8588e007d46bd8544f16319e558637c87a504eac6972c9720bcab2916c913988 |
| spot_check.py | Funnel step 4 genre spot-check (embedded prompt; GenreClassifier shared with the deep fetch) | 13232 | 01d9eec51d78af1350cb21f5409fe82a20f66811f1db535339bc237dfed1ad3d |
| t0_schema_discovery.py | Bottom-up B2B template schema discovery + consolidation with embedded prompts | 7899 | 61e602ca61899c022bafc658a34f16f31167ace6aee88916a19c3478d2477f23 |
| temporal_control.py | Era-task temporal control (battery 8.7 scan side) | 7195 | 81f4573bd5d4d6f11503393a650f24601cec66a928b6498dc5ff1bf5d392c822 |
| verify_reference.py | Drift gate: pinned vendor commit, declared deviation set, fork-patch coverage, declared model config | 5617 | fadff98f6658654566eb1c6e39edd3836d861dcd532f0d23d7f87599851cdfac |

## fetch/ - corpus reconstruction (see fetch/README.md)

| File | Purpose | Bytes | sha256 |
|---|---|---|---|
| README.md | Deterministic rebuild guide, corpus manifest and funnel file map | 4934 | 156b245fc61c6392f48197cd258da751fca57d9d6bdbf18f8eed0e1d7db0e805 |
| corpus_manifest.csv | Authoritative kept-list: all 2,250 frozen corpus documents with Wayback fetch coordinates (text-free export of the frozen parquet) | 732411 | cd2ac12807eaf34165e0c85bfd05994e372a39721c0a699d9202d023fae645e2 |
| ledger.csv | Main fetch ledger: every fetched candidate URL with Wayback snapshot id, filter outcome, drop reason | 6722942 | d25bf7c3b6605204488b1a8b9cf72f6930e2863741f1b55b151d8d16483695e2 |
| ledger_pass1.csv | First-pass fetch ledger (earlier fetch batch; see the coverage note in fetch/README.md) | 458970 | 75160773ad3fdd039923a92a0ff1dbdab3f0a2e91a9d248934bd3cbfd98264a0 |
| corpus_domains_selected.csv | Step 5 industry-quota selection: the 306 selected domains | 73978 | 6b62398146164394f05bd22aba25a69187f47ac3f04f8530f1523f39e77a1f32 |
| qualified_domains.csv | Step 3 archive-volume survivors (698 qualified) | 62039 | 13312a4176609815800d4eeedb9e097b6d48de1111dd8c7bf68e01ccbcd8eb2a |
| domains_composite.csv | Step 3 CDX qualification results over the screened composite frame | 161567 | 6b21bc6fcc48eb50992e372c1acc380ac8b828c0b8936eec468066312f9d1f23 |
| spotcheck/posts.csv | Step 4 per-domain probe results (language, genre, usability per sampled post) | 530093 | c538013634a8356e401dcd1dd9999914177178746506602654d76c93df0ef175 |
| spotcheck/decision_list.csv | Step 4 per-domain decisions | 147071 | b012426a441ec8bc409b588e3e906051c864de9af6a8817a85753edc3099a271 |
| spotcheck/decision_list_kept.csv | Steps 4-5 output of study_b/derive_kept.py: the kept domain set (306 rows; see self-check item 5 on the funnel's 307 keep-eligible count) | 73978 | c60744ac8305ff070f2b6120607eaa1897b8e78defbe00f5fecfeaace12c4909 |
| frames/frame_inc5000.csv | Step 1 Inc5000 source frame | 1085127 | 4bb33d3a51cae7cc9d4f2d02c7c17ccc510c735e4d0f1f08169b8314e138b2b1 |
| frames/frame_ft1000.csv | Step 1 FT1000 source frame | 115736 | fd5d246ae4ff3fe32c913338eb575f79988ed9f2bcfd5f863defc24077fac259 |
| frames/frame_g2.csv | Step 1 G2 source frame | 43813 | 6b4ff419f04e3c4e2ebdc2f7783f29d5768f5c4903d2ed5c1f27b772995da5a1 |
| frames/PROVENANCE_inc5000.md | Inc5000 source provenance (URL + sha256 of raw lists) | 4330 | 024316df969ae414ae85c40eb25ef220ef5c18df4a5cd7f920f477b6d6226ff9 |
| frames/PROVENANCE_ft1000.md | FT1000 source provenance | 6986 | 13e9ab6065f1fec3aad5f4c27542913c0c6214be33fd581ea516933a5ff3c64a |
| frames/PROVENANCE_g2.md | G2 source provenance | 15342 | b9aef407b94a90ef413dd81f2650912afa7874af1f55d78ce5a353c27aec33e7 |
| frames/composite_frame.csv | Step 1 composite frame (15,075 domains + YC frame rows) | 1262392 | dd288835fd3f3ac9827463f4fbb5392ba9ba611a1e2bbe5951feefd5e1d54b55 |
| frames/composite_frame_screened.csv | Steps 1-2 output: composite frame after prefilter and company-fit screen | 1473603 | 8c408aaca72814a9cdff7e77ae60265305d4a9a5a08b72c23abd416d9a84e5f3 |
| frames/f1_dropped.csv | Step 1 anti-persona prefilter drops (10.4%) with rule hit | 170807 | 10f5eeeda2134663ef23983bc628e8d3b99d59efb271b09da604ebeee57800eb |
| frames/icp_screen.jsonl | Step 2 per-domain company-fit decisions: keep/drop, vertical, one-line reason | 10103944 | 270cfca426e517641ad41119b37dc91c4c91232d6d2f53e50c94a138c81c92da |

## GATED ITEMS - exist, not included

Available to researchers on request under a non-commercial research
agreement. Rationale in the paper's Statements section and README.md. Request
process: email jochen@sitefire.ai (non-commercial research agreement).
Sizes are of the current stored artifacts.

| Item | Size | Note |
|---|---|---|
| Per-document feature answers (148,500 = 13,500 texts x 11 dimensions) | ~160 MB | Stage-5 raw outputs; the encoded matrix below derives from them |
| Encoded feature matrix (12,900 x 868, features_encoded.parquet) | ~1.9 MB | sha256 prefix committed in the freeze manifest (05f43e8cc49e9917) |
| Per-document rarity values | ~420 KB | Basis of the violin figure and tail tables |
| Trained classifier models | refit on demand | Weights are not persisted; the released scripts refit deterministically from the encoded matrix and assert the published headline (0.9803) on refit; serialized weights supplied with the gated bundle |
| Briefs (2,250) | ~2.4 MB | Derived from copyrighted posts |
| Mirrors (11,250) | ~102 MB | Generated by the five models from the briefs |
| Rewritten test mirrors (1,450, one JSONL per model) | ~12 MB | Stage-6 self-rewrites of the test mirrors; sha256 prefixes recorded in artifacts/r7/durability_aggregates.json regeneration output |
| Rewritten-post feature answers (15,950 = 1,450 x 11 dimensions) | ~2 MB | Stage-6 rescore outputs |
| Encoded rewritten matrix (1,450 x 868, features_encoded_rewritten.parquet) | ~0.8 MB | sha256 prefix 554dceeeebe3fdff (asserted in the durability evaluation) |
| Templates (13,500 structural summaries) | ~158 MB | Stage-2 intermediates, derived from the documents |
| Gold-session annotation sheets and mini-validation sheet | ~50 KB | Embed full document texts; scored results are public (artifacts/gold/, artifacts/r5_gate/) |

Not distributed in any tier: the human post texts themselves (copyrighted;
reconstruct via fetch/).

## SELF-CHECK (package review, 2026-08-20; durability additions and the analysis-code/prompt/license pass, 2026-08-31)

Performed against the release posture (METHODOLOGY.md section 10) before
finalizing.

**Gating check - nothing included that should be gated.** No post texts,
briefs, mirrors, rewritten mirrors, templates, per-document answers, or
model weights are in the package. Specifically excluded on this ground: MINI_VALIDATION_SHEET.md
(embeds five full document texts); its sample definition (pack.json) and
verdicts (MINIVALIDATION_VERDICTS.json) are included instead. The ledger and
funnel files carry URLs, snapshot ids, titles, and decisions only.
DRAW_1_MANIFEST.json and pack.json carry doc ids and titles, no bodies.

**Canonicality check - one canonical source per number.** The package
carries only the faithful-protocol result artifacts the paper's numbers
trace to; working copies and intermediate computations superseded during
review are not distributed.

**Completeness check - known gaps, disclosed rather than papered over:**
1. Two prose check values are carried by the canonical prose record rather
   than a distributed JSON artifact: the year-task-at-chance CV F1 (0.49)
   and the post-cutoff entity-scan rate (0.08%).
   Their canonical statement is METHODOLOGY.md battery rows 8.5/8.7 and they are
   recomputable (study_b/temporal_control.py, study_b/r6_battery_tail.py);
   the faithful-protocol exclusion checks that carry the paper's conclusions
   ARE included (review2_fixes.json).
2. Trained model weights are not persisted anywhere in the study storage;
   "trained models" in the gated tier means deterministic refits (asserted
   against the published headline) serialized at request time. Flagged for
   the PI to confirm this wording matches the paper's Statements intent.
3. Citation and DOI are placeholders pending publication. The LICENSE file
   and the gated-access contact are in place.
4. Figure PDFs (vector versions) exist alongside the released PNGs and were
   omitted for size; the PNGs are the 300-dpi paper versions.
5. Ledger coverage, found during this package's own audit and fixed inside
   the package: the two fetch ledgers' kept rows cover 2,216 of the 2,250
   frozen documents (34 retry-pass rows were overwritten by later fetch
   batches). corpus_manifest.csv, a text-free export of the frozen parquet,
   was added as the authoritative kept-list with full Wayback coordinates
   for all 2,250; the ledgers remain the rejected-candidate record.
   Relatedly, the funnel's 307 keep-eligible count is not directly a row
   count of any single included file (decision_list_kept.csv holds the 306
   selected; the raw posts_usable>=2 filter over decision_list.csv gives
   313 before the retro ICP dedupe in study_b/derive_kept.py). Flagged for
   the PI: confirm the 307 derivation is reproducible from the committed
   inputs, or adjust the Table 1 caption to cite the derivation script.

**Reviewer-needs check.** A reviewer can: verify every paper table and
robustness check against included JSON/MD artifacts (VERIFICATION.md);
verify the rewording-durability numbers against
artifacts/r7/durability_aggregates.json and the gate record in
artifacts/r7/GATES.md; inspect all 214 feature definitions with menus and
every exclusion with its reason; read every prompt including both screen
prompts and the rewording-attack prompt; audit the funnel end-to-end from
frame to ledger; check the pre-training freeze via four in-package hash
matches; and rebuild the corpus without any LLM call.

**Total package size: 27 MB (148 files).** fetch/ is 22 MB (the two largest
files are frames/icp_screen.jsonl at 10.1 MB and ledger.csv at 6.7 MB, both
funnel-transparency data); artifacts/ 2.5 MB (2.0 MB of that the rendered
figures); instrument/ 1.1 MB; prompts/ and code/ 0.2 MB.
