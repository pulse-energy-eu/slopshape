# Corpus reconstruction

The human corpus is not redistributed (the posts are copyrighted). It is
reconstructable deterministically: every document is a Wayback Machine
snapshot identified in ledger.csv, and every funnel decision that selected it
is committed here. Rebuilding requires no LLM call for the corpus itself - the
funnel's LLM decisions (ICP screen, genre spot-check) are already recorded in
the decision files; the fetch step replays archived snapshots.

## The corpus manifest and the ledgers (the corpus, minus the text)

corpus_manifest.csv - the authoritative kept-list: exactly the 2,250 frozen
corpus documents with doc_id, domain, stratum, vertical, title, word count,
snapshot timestamp, live URL, and Wayback snapshot URL. Exported from the
frozen corpus parquet with the text column removed; fetching each wayback_url
and extracting the article body reproduces the corpus, and
study_b/freeze_corpus.py reproduces the frozen parquet from it.

ledger.csv and ledger_pass1.csv - the full fetch provenance: one row per
fetched candidate URL across both fetch passes, including every rejected
candidate with its drop_reason from the filter chain (length 600-2,500 words,
language, genre, near-duplicate). Coverage note, disclosed: the main ledger's
kept rows (2,058) plus the pass-1 ledger's kept rows cover 2,216 of the 2,250
frozen documents; 34 documents entered during retry passes whose ledger rows
were overwritten by later fetch batches. corpus_manifest.csv closes that gap:
it is derived from the frozen parquet itself and lists all 2,250 with full
fetch coordinates, so reconstruction never depends on ledger completeness.
The ledgers remain the record of what was tried and why candidates were
dropped.

## Funnel decision files (paper Table 1, steps 1-5)

| Step | File(s) | Content |
|---|---|---|
| 1. Frame assembly | frames/frame_inc5000.csv, frames/frame_ft1000.csv, frames/frame_g2.csv + frames/PROVENANCE_*.md | Source frames with per-source provenance records (source URL + sha256 of the raw archived lists). The YC frame enters through the composite file below; raw source dumps are re-downloadable per the provenance records. |
| 1. Composite frame + anti-persona prefilter | frames/composite_frame.csv, frames/composite_frame_screened.csv, frames/f1_dropped.csv | 15,075-domain composite frame; the deterministic anti-persona category prefilter's drops (10.4%) listed with rule hit |
| 2. Company-fit screen | frames/icp_screen.jsonl | Per-domain keep/drop + normalized vertical + one-line reason (gpt-5.6-luna, 2 votes; prompt in study_b/icp_screen.py) |
| 3. Archive-volume check | domains_composite.csv, qualified_domains.csv | Wayback CDX archive counts; qualified = >= 25 archived pre-2022-11-30 article URLs |
| 4. Genre spot-check | spotcheck/posts.csv, spotcheck/decision_list.csv, spotcheck/decision_list_kept.csv | Per-domain probe results (5 posts: language, genre, usability) and the keep-eligible derivation |
| 5. Industry quotas | corpus_domains_selected.csv | The 306 selected domains under the published vertical quota rules (software cap 40%) |
| 6. Fetch and filter + freeze | ledger.csv | Per-URL fetch and filter outcomes (see above) |

## Deterministic rebuild

Scripts (repository paths), in funnel order, all resume-safe with committed
seeds and parameters in-script:

1. study_b/build_composite_frame.py - step 1 (deterministic; reproduces composite_frame_screened.csv from the frame files)
2. study_b/icp_screen.py - step 2 (only needed to re-audit; decisions are committed in frames/icp_screen.jsonl)
3. study_b/find_domains.py, frame set to composite (frame file frames/composite_frame_screened.csv) - step 3 Wayback CDX qualification (network-bound, overnight pace)
4. study_b/spot_check.py + study_b/derive_kept.py - step 4
5. study_b/build_corpus.py select - step 5 (deterministic quota rules; reproduces corpus_domains_selected.csv)
6. study_b/build_corpus.py fetch - step 6, the deep fetch through the filter chain (seed 202607; writes ledger.csv and the corpus parquet; paced ~3.5 s/request against web.archive.org, expect roughly 2-4 unattended days for the full corpus)
7. study_b/freeze_corpus.py - freeze (vertical normalization, frozen parquet)

To verify rather than rebuild from the open web: replay corpus_manifest.csv
directly (the fetch step fast-paths already-ledgered domains). Expected
result: 2,250 documents over 268 domains; corpus-level statistics to match
are in artifacts/METHODOLOGY.md section 2.1. Wayback snapshots are stable
but not guaranteed eternal; the snapshot timestamp in the ledger pins the
exact capture.

Downstream generation (briefs via study_b/extract_briefs.py, mirrors via
study_b/generate_mirrors.py) requires API access to the five generator models
and reproduces the gated document sets; measured cost was ~$160 for briefs
plus mirrors at 2026 prices. See code/README.md for the full stage map and
model requirements.

