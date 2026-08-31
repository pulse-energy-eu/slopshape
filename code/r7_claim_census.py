"""R7 claim-preservation census: judge ALL rewrite pairs, not a 50-sample.

Follow-up to the seeded 50-pair gate, which proved too noisy at n=50 (0.88
and 0.92 readings on near-identical samples): the claim check is instead run
as a census over all 1,450 pairs, followed by a QC loop that regenerates
every "no" doc (max 2 regeneration attempts) and re-judges it.

Judge, prompt, and parsing are r7_verify_rewrites' verbatim (imported).
Results go to outputs/study_b/r7/claim_census.jsonl, keyed by
(source, doc_id, md5 of the rewritten text) - so re-running after a
regeneration automatically re-judges exactly the docs whose text changed,
and the file keeps the full judgment history across QC passes. The final
census rate is computed over each doc's CURRENT text only.

Usage:
  .venv/bin/python -m study_b.r7_claim_census [--concurrency 8]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

from study_b.generate_mirrors import MODELS
from study_b.r7_lamp_rewrite import OUT, SPLITS, gemini_api_key, load_test_mirrors
from study_b.r7_verify_rewrites import JUDGE_MODEL, JUDGE_PROMPT

CENSUS = OUT / "claim_census.jsonl"


def text_hash(t: str) -> str:
    return hashlib.md5(t.encode()).hexdigest()


def load_pairs() -> list[dict]:
    splits = json.load(open(SPLITS))
    test_ids = {d for d, s in splits["doc_split"].items() if s == "test"}
    pairs = []
    for key in MODELS:
        path = OUT / f"rewritten_{key}.jsonl"
        if not path.exists():
            continue
        originals = {d["doc_id"]: d for d in load_test_mirrors(key, test_ids)}
        for line in open(path):
            if not line.strip():
                continue
            r = json.loads(line)
            o = originals.get(r["doc_id"])
            if not o:
                continue
            pairs.append({"doc_id": r["doc_id"], "source": key,
                          "original_text": o["text"],
                          "rewritten_text": r["rewritten_text"],
                          "hash": text_hash(r["rewritten_text"])})
    return pairs


def judge_one(client, p: dict) -> dict:
    prompt = (JUDGE_PROMPT
              .replace("{orig}", p["original_text"])
              .replace("{rew}", p["rewritten_text"]))
    verdict, note, in_tok, out_tok = "judge_error", "", 0, 0
    for attempt in range(4):
        try:
            r = client.models.generate_content(model=JUDGE_MODEL,
                                               contents=prompt)
            um = r.usage_metadata
            in_tok += um.prompt_token_count or 0
            out_tok += ((um.candidates_token_count or 0)
                        + (getattr(um, "thoughts_token_count", 0) or 0))
            m = re.search(r'"same_claims"\s*:\s*"(yes|no)"', r.text or "", re.I)
            if m:
                verdict = m.group(1).lower()
                nm = re.search(r'"note"\s*:\s*"([^"]*)"', r.text or "")
                note = nm.group(1) if nm else ""
                break
            raise ValueError("no verdict in response")
        except Exception as e:
            note = str(e)[:120]
            time.sleep(5 * (attempt + 1))
    return {"doc_id": p["doc_id"], "source": p["source"], "hash": p["hash"],
            "same_claims": verdict, "note": note,
            "in_tokens": in_tok, "out_tokens": out_tok,
            "ts": round(time.time())}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--concurrency", type=int, default=8)
    args = ap.parse_args()

    pairs = load_pairs()
    done = set()
    if CENSUS.exists():
        for l in open(CENSUS):
            if l.strip():
                j = json.loads(l)
                if j["same_claims"] in ("yes", "no"):
                    done.add((j["source"], j["doc_id"], j["hash"]))
    todo = [p for p in pairs if (p["source"], p["doc_id"], p["hash"]) not in done]
    print(f"census: {len(pairs)} pairs, {len(todo)} to judge "
          f"({len(done)} already judged at current text)", file=sys.stderr)

    from google import genai
    client = genai.Client(api_key=gemini_api_key())
    lock = Lock()
    n = 0
    with open(CENSUS, "a") as f, \
            ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = [ex.submit(judge_one, client, p) for p in todo]
        for fut in as_completed(futs):
            res = fut.result()
            with lock:
                f.write(json.dumps(res) + "\n")
                n += 1
                if n % 50 == 0:
                    f.flush()
                    print(f"  [{n}/{len(todo)}]", file=sys.stderr)

    # final tally over current texts only
    latest = {}
    for l in open(CENSUS):
        if not l.strip():
            continue
        j = json.loads(l)
        latest[(j["source"], j["doc_id"], j["hash"])] = j
    current = {(p["source"], p["doc_id"], p["hash"]): p for p in pairs}
    verdicts = [latest.get(k, {"same_claims": "missing"}) for k in current]
    n_yes = sum(1 for v in verdicts if v["same_claims"] == "yes")
    n_no = sum(1 for v in verdicts if v["same_claims"] == "no")
    n_other = len(verdicts) - n_yes - n_no
    _, pin, pout = MODELS["gemini"]
    usd = sum((j["in_tokens"] / 1e6) * pin + (j["out_tokens"] / 1e6) * pout
              for j in latest.values())
    print(json.dumps({
        "n_pairs": len(pairs), "yes": n_yes, "no": n_no,
        "error_or_missing": n_other,
        "rate": round(n_yes / max(n_yes + n_no, 1), 4),
        "judge_usd_all_passes": round(usd, 2),
        "by_model_no": {k: sum(1 for (s, _, _), v in
                               zip(current.keys(), verdicts)
                               if s == k and v["same_claims"] == "no")
                        for k in MODELS},
    }, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
