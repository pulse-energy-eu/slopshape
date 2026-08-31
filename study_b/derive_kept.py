#!/usr/bin/env python
"""Derive spotcheck/decision_list_kept.csv from decision_list.csv.

The original keep-filter step did not survive the 2026-08-01 data loss (only
its READER in build_corpus.py did). Rule reconstructed from the published
corpus funnel (study_b/corpus_snapshot.md): a domain is keep-eligible iff the
spot-check verified >= 2 usable informational posts.

  .venv/bin/python -m study_b.derive_kept
"""
import sys
from pathlib import Path

import pandas as pd

SRC = Path("outputs/study_b/spotcheck/decision_list.csv")
DST = Path("outputs/study_b/spotcheck/decision_list_kept.csv")
MIN_USABLE = 2


def main() -> int:
    import json
    df = pd.read_csv(SRC)
    # v2: only ICP-screened-in domains may enter selection
    screen = {json.loads(l)["domain"]: json.loads(l)["keep"]
              for l in open("outputs/study_b/frames/icp_screen.jsonl")}
    df = df[df.domain.map(lambda d: screen.get(d, False))]
    kept = df[pd.to_numeric(df.posts_usable, errors="coerce").fillna(0) >= MIN_USABLE]
    kept.to_csv(DST, index=False)
    print(f"kept {len(kept)}/{len(df)} domains (rule: posts_usable >= {MIN_USABLE}); "
          f"est usable posts total: {int(pd.to_numeric(kept.est_usable_total, errors='coerce').fillna(0).sum())}")
    return 0 if len(kept) >= 60 else 1


if __name__ == "__main__":
    sys.exit(main())
