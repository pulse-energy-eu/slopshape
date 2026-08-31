#!/usr/bin/env python
"""Freeze the regenerated human corpus: story_human.parquet -> story_human_frozen.parquet.

Replaces reextract_human for the 2026-08 regeneration: that tool REPAIRS an
existing frozen corpus (decode corruption in the pre-2026-07-25 extraction
path) and cannot bootstrap one. build_corpus now extracts through the fixed
trafilatura path already (fingerprint check: 3/302 marginal hits on pass 1),
so freezing = apply the symmetric normalizer (study_b.normalize, identical
rule set as the recorded protocol) + drop residual-corruption docs + write.

  .venv/bin/python -m study_b.freeze_corpus
"""
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from study_b.normalize import normalize  # noqa: E402

SRC = Path("outputs/study_b/corpus/story_human.parquet")
DST = Path("outputs/study_b/corpus/story_human_frozen.parquet")
CORRUPT = re.compile(r"[\xc2-\xf4](\s|$)")
# canonical 7 strata; v1 YC domains carry legacy labels
VERT_MAP = {"saas": "software_saas", "ecommerce": "ecommerce_retail",
            "fintech": "fintech_insurance", "other": "services_other"}


def main() -> int:
    df = pd.read_parquet(SRC)
    n0 = len(df)
    df["story_human"] = df.story_human.astype(str).map(normalize)
    df["vertical"] = df.vertical.map(lambda v: VERT_MAP.get(v, v))
    bad = df.story_human.map(lambda t: bool(CORRUPT.search(t)))
    df = df[~bad].reset_index(drop=True)
    df["words"] = df.story_human.str.split().str.len()
    df.to_parquet(DST)
    print(f"frozen: {len(df)} docs (from {n0}; {int(bad.sum())} dropped for "
          f"residual decode corruption); median words {df.words.median():.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
