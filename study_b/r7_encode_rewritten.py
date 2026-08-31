#!/usr/bin/env python
"""R7 durability: encode the rescored LAMP-rewritten answers with the FROZEN
r6 encoder (artifacts/METHODOLOGY.md stage 6).

Same scheme as study_b.r6_build (D9): one-hot binary/categorical, multi-hot
multi_select, ordinal position, NaN missing. Same instrument (214 surviving
features), same column construction - the resulting encoded column set is
asserted EQUAL to outputs/study_b/r6/features_encoded.parquet before writing.

Outputs:
  outputs/study_b/r7/features_encoded_rewritten.parquet  (1,450 rows)
  outputs/study_b/r7/eval_matrix_manifest.json           (counts, hashes, map)

  .venv/bin/python -m study_b.r7_encode_rewritten
"""
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from study_b.r5_qa import canon  # noqa: E402
from study_b.r6_build import surviving_features  # noqa: E402

R6 = Path("outputs/study_b/r6")
R7 = Path("outputs/study_b/r7")


def main() -> int:
    import numpy as np
    import pandas as pd

    feats = surviving_features()
    print(f"instrument: {len(feats)} features "
          f"({sum(f['is_style'] for f in feats)} style)", file=sys.stderr)

    # ---- collect answers for surviving features (frozen logic, r7 input)
    want = {f["id"] for f in feats}
    answers = defaultdict(dict)  # (doc_id, source) -> {fid: canon}
    for l in open(R7 / "answers_rewritten.jsonl"):
        r = json.loads(l)
        if "answers" in r:
            for fid, v in r["answers"].items():
                if fid in want:
                    answers[(r["doc_id"], r["source"])][fid] = canon(v)
    print(f"rewritten texts with answers: {len(answers)}", file=sys.stderr)

    # ---- column construction (identical to r6_build)
    cols = {}
    for f in feats:
        vals = [canon(v) for v in f.get("values", [])]
        if f.get("type") == "multi_select":
            for v in vals:
                cols[f"{f['id']}__{v}"] = ("multi", f["id"], v)
        elif f.get("type") in ("ordinal", "scale"):
            cols[f"{f['id']}__ord"] = ("ord", f["id"], vals)
        else:
            for v in vals:
                cols[f"{f['id']}__{v}"] = ("onehot", f["id"], v)
    col_names = sorted(cols)

    # ---- HARD ASSERT: byte-identical column layout vs the frozen matrix
    frozen = pd.read_parquet(R6 / "features_encoded.parquet")
    frozen_enc = [c for c in frozen.columns if "__" in c]
    assert col_names == frozen_enc, (
        f"column mismatch: {len(col_names)} built vs {len(frozen_enc)} frozen; "
        f"only_built={sorted(set(col_names) - set(frozen_enc))[:5]} "
        f"only_frozen={sorted(set(frozen_enc) - set(col_names))[:5]}")
    print(f"encoded columns: {len(col_names)} == frozen layout OK",
          file=sys.stderr)

    h = pd.read_parquet("outputs/study_b/corpus/story_human_frozen.parquet")
    meta_by_doc = {r.doc_id: (r.domain, r.vertical, r.stratum)
                   for r in h.itertuples()}

    rows, metas = [], []
    for (doc_id, source), fa in sorted(answers.items()):
        row = np.full(len(col_names), np.nan, dtype=np.float32)
        for j, cn in enumerate(col_names):
            kind, fid, spec = cols[cn]
            a = fa.get(fid)
            if a is None:
                continue
            if kind == "onehot":
                row[j] = 1.0 if a == spec else 0.0
            elif kind == "multi":
                parts = set(a.split("|")) if a else set()
                row[j] = 1.0 if spec in parts else 0.0
            else:  # ordinal
                row[j] = float(spec.index(a)) if a in spec else np.nan
        dom, vert, strat = meta_by_doc.get(doc_id, ("", "", ""))
        rows.append(row)
        metas.append({"doc_id": doc_id, "source": source,
                      "label_ai": 0 if source == "human" else 1,
                      "domain": dom, "vertical": vert, "stratum": strat})
    X = pd.DataFrame(np.vstack(rows), columns=col_names)
    M = pd.DataFrame(metas)
    df = pd.concat([M, X], axis=1)
    assert list(df.columns) == list(frozen.columns), "full layout mismatch"
    df.to_parquet(R7 / "features_encoded_rewritten.parquet")
    print(f"matrix: {len(df)} texts x {len(col_names)} columns", file=sys.stderr)

    # ---- manifest
    splits = json.load(open(R6 / "splits.json"))["doc_split"]
    doc_map = [{"doc_id": d, "source": s, "orig_split": splits.get(d, "MISSING")}
               for (d, s) in sorted(answers.keys())]
    col_hash = hashlib.sha256("\n".join(df.columns).encode()).hexdigest()
    frozen_col_hash = hashlib.sha256(
        "\n".join(frozen.columns).encode()).hexdigest()
    assert col_hash == frozen_col_hash
    manifest = {
        "rows": len(df),
        "docs": int(df.doc_id.nunique()),
        "sources": {s: int(n) for s, n in
                    df.source.value_counts().sort_index().items()},
        "encoded_columns": len(col_names),
        "column_hash_sha256": col_hash,
        "column_hash_matches_frozen": True,
        "frozen_matrix": str(R6 / "features_encoded.parquet"),
        "matrix_sha256_16": hashlib.sha256(
            (R7 / "features_encoded_rewritten.parquet")
            .read_bytes()).hexdigest()[:16],
        "all_docs_in_test_split": all(
            m["orig_split"] == "test" for m in doc_map),
        "doc_id_mapping": doc_map,
    }
    json.dump(manifest, open(R7 / "eval_matrix_manifest.json", "w"), indent=2)
    print("manifest written", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
