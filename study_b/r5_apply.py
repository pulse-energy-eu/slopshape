#!/usr/bin/env python
"""R5: feature application.

Scores taxonomy features over texts with gemini-3.6-flash, minimal thinking
(D13). ALL 266 features are applied (style features included - the strict
boundary is an ANALYSIS-time exclusion; Style-only/Narr+Style variants need
style scores).

Modes:
  aspect  one call per (text, dimension) - the paper's protocol (default)
  single  one call per text with all features (coverage-check comparator)

Gate finding 2026-08-14 baked in: single-choice features (binary/categorical/
ordinal/scale) are forced to EXACTLY ONE verbatim value; multi_select answers
a subset list.

Resume-safe: one JSONL row per call keyed (tag, doc_id, source, dim);
reruns skip completed keys. Spend tracked from usage; --max-usd hard cap.

  .venv/bin/python -m study_b.r5_apply --tag full [--mode aspect] [--docs FILE]
  .venv/bin/python -m study_b.r5_apply --tag repeat_1 --docs outputs/study_b/r5/repeat_docs.json
"""
import argparse
import concurrent.futures as cf
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from study_b.generate_mirrors import GATEWAY  # noqa: E402

MODEL = "gemini-3.6-flash"  # native Google API; gateway shim cannot disable thinking
API = "https://generativelanguage.googleapis.com/v1beta/models"
PIN, POUT = 0.75, 3.75  # $/M: Google-direct INTRODUCTORY pricing through
# 2026-12-31 (verified 2026-08-15 via multiple sources; standard/gateway rates
# are 1.5/7.5 - the earlier projection used those and overstated 2x).
# Cache-hit input bills lower still ($0.15/M); counter stays conservative.
TAX = Path("outputs/study_b/r3/dedup/condensed_taxonomy_0.85.json")
OUT = Path("outputs/study_b/r5")
SINGLE_CHOICE_TYPES = {"binary", "categorical", "ordinal", "scale"}

# TEXT FIRST: a doc's aspect calls share the post as an identical prefix, so
# Gemini implicit caching discounts the re-sent text across the 11 calls.
PROMPT = """You will annotate the B2B blog post below against fixed features.

POST:
{text}

---

Annotate the post above against these {n} features{dim_note}.

Rules:
- Judge only what is in the text.
- Single-choice features (marked ONE): answer with EXACTLY ONE allowed value, \
verbatim. Never several, never a paraphrase.
- Multi-select features (marked MANY): answer with a JSON list containing every \
allowed value that applies (may be empty).
- If a feature is genuinely inapplicable, use the closest allowed value (e.g. \
"none"/"absent" variants) - never invent values, never omit a feature.

FEATURES:
{features}

Return ONLY a JSON object mapping EVERY feature id to its answer, e.g.
{{"PUR_JOB_001": "explain", "EVD_MIX_002": ["proprietary data"]}}. All {n} ids \
must be present."""


def load_features() -> dict:
    """dim -> list of feature dicts (id, question, type, values)."""
    raw = json.load(open(TAX))
    raw = raw.get("feature_taxonomy", raw)
    by_dim = defaultdict(list)
    for dim, dbody in raw.items():
        if not isinstance(dbody, dict):
            continue
        for abody in (dbody.get("aspects") or {}).values():
            for f in abody.get("features") or []:
                if isinstance(f, dict) and f.get("id"):
                    by_dim[dim].append(f)
    return dict(by_dim)


def feature_block(feats: list[dict]) -> str:
    lines = []
    for f in feats:
        mode = "MANY" if f.get("type") == "multi_select" else "ONE"
        vals = " | ".join(map(str, f.get("values", [])))
        lines.append(f"{f['id']} [{mode}]: {f.get('question','')} "
                     f"ALLOWED: {vals}")
    return "\n".join(lines)


def iter_texts(doc_filter: set | None = None):
    import pandas as pd
    h = pd.read_parquet("outputs/study_b/corpus/story_human_frozen.parquet")
    for r in h.itertuples():
        if doc_filter is None or r.doc_id in doc_filter:
            yield {"doc_id": r.doc_id, "source": "human", "text": r.story_human}
    for f in sorted(Path("outputs/study_b/mirrors").glob("story_*.jsonl")):
        for line in open(f):
            r = json.loads(line)
            if doc_filter is None or r["doc_id"] in doc_filter:
                yield {"doc_id": r["doc_id"], "source": r["source"],
                       "text": r["text"]}


class Applier:
    def __init__(self):
        import requests
        self.session = requests.Session()
        self.key = os.environ.get("GEMINI_API_KEY_1") or os.environ["GEMINI_API_KEY"]
        self.spent = 0.0

    def call(self, item: dict, dim: str, feats: list[dict], tag: str) -> dict:
        n = len(feats)
        dim_note = f' of the dimension "{dim}"' if dim != "ALL" else ""
        prompt = PROMPT.format(n=n, dim_note=dim_note,
                               features=feature_block(feats),
                               text=" ".join(item["text"].split()[:2600]))
        for attempt in range(5):
            try:
                r = self.session.post(
                    f"{API}/{MODEL}:generateContent?key={self.key}",
                    json={"contents": [{"parts": [{"text": prompt}]}],
                          "generationConfig": {
                              "maxOutputTokens": 6000,
                              "thinkingConfig": {"thinkingLevel": "minimal"}}},
                    timeout=300)
                if r.status_code == 429:
                    time.sleep(20 * (attempt + 1))
                    continue
                r.raise_for_status()
                d = r.json()
                cand = d["candidates"][0]
                txt = "".join(p.get("text", "")
                              for p in cand.get("content", {}).get("parts", []))
                um = d.get("usageMetadata", {})
                tin = um.get("promptTokenCount", 0)
                tout = (um.get("candidatesTokenCount", 0)
                        + um.get("thoughtsTokenCount", 0))
                self.spent += (tin * PIN + tout * POUT) / 1e6
                m = re.search(r"\{.*\}", txt, re.S)
                ans = json.loads(m.group(0) if m else txt)
                known = {f["id"] for f in feats}
                ans = {k: v for k, v in ans.items() if k in known}
                if len(ans) < n * 0.9 and attempt < 4:
                    raise ValueError(f"coverage {len(ans)}/{n}")
                return {"tag": tag, "doc_id": item["doc_id"],
                        "source": item["source"], "dim": dim, "answers": ans,
                        "n_expected": n,
                        "usage": {"in": tin, "out": tout,
                                  "cached": um.get("cachedContentTokenCount", 0)}}
            except Exception as e:
                if attempt == 4:
                    return {"tag": tag, "doc_id": item["doc_id"],
                            "source": item["source"], "dim": dim,
                            "error": str(e)[:200]}
                time.sleep(6 * (attempt + 1))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True,
                    help="run tag: full, repeat_1..5, cov_aspect, cov_single")
    ap.add_argument("--mode", choices=["aspect", "single"], default="aspect")
    ap.add_argument("--docs", default=None,
                    help="JSON file with doc_id list (subset runs)")
    ap.add_argument("--concurrency", type=int, default=16)
    ap.add_argument("--max-usd", type=float, default=650.0)
    args = ap.parse_args()

    by_dim = load_features()
    n_feats = sum(len(v) for v in by_dim.values())
    print(f"taxonomy: {n_feats} features across {len(by_dim)} dims", file=sys.stderr)

    doc_filter = None
    if args.docs:
        doc_filter = set(json.loads(Path(args.docs).read_text())["doc_ids"])
    texts = list(iter_texts(doc_filter))
    print(f"texts: {len(texts)}", file=sys.stderr)

    if args.mode == "aspect":
        units = [(t, dim, feats) for t in texts for dim, feats in sorted(by_dim.items())]
    else:
        all_feats = [f for _, fs in sorted(by_dim.items()) for f in fs]
        units = [(t, "ALL", all_feats) for t in texts]

    OUT.mkdir(parents=True, exist_ok=True)
    outfile = OUT / f"answers_{args.tag}.jsonl"
    done = set()
    if outfile.exists():
        for l in open(outfile):
            r = json.loads(l)
            if "answers" in r:
                done.add((r["doc_id"], r["source"], r["dim"]))
    todo = [u for u in units if (u[0]["doc_id"], u[0]["source"], u[1]) not in done]
    print(f"calls: {len(todo)} to run ({len(done)} done)", file=sys.stderr)

    app = Applier()
    n_ok = n_err = 0
    t0 = time.time()
    with open(outfile, "a") as fh, cf.ThreadPoolExecutor(args.concurrency) as ex:
        for i, rec in enumerate(
                ex.map(lambda u: app.call(u[0], u[1], u[2], args.tag), todo), 1):
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            n_ok += "answers" in rec
            n_err += "error" in rec
            if i % 200 == 0:
                rate = i / max(1, time.time() - t0) * 3600
                print(f"  [{i}/{len(todo)}] ok={n_ok} err={n_err} "
                      f"spent=${app.spent:.2f} rate={rate:.0f}/h", file=sys.stderr)
            if app.spent > args.max_usd:
                print(f"STOPPED: spend cap ${args.max_usd}", file=sys.stderr)
                return 1
    print(f"done tag={args.tag}: {n_ok} ok, {n_err} failed (rerun to retry), "
          f"spend ${app.spent:.2f}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
