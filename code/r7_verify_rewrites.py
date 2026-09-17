"""R7 gate: verify LAMP rewrites before scoring (see r7_lamp_rewrite.py).

Four gates over outputs/study_b/r7/rewritten_{model}.jsonl vs the original
test-split mirrors:

  (a) length drift   - rewritten/original word ratio must sit in [0.6, 1.4];
                       reports the ratio distribution and every violation.
  (b) trivial copy   - >90% of the rewrite's 13-grams already present in the
                       original means no real edit happened; flag it.
  (c) refusal scan   - empty / <100-word outputs and refusal-phrased openings.
  (d) claim check    - sample of original/rewritten pairs (default 50,
                       seed 202616; --sample 0 = all available), one
                       gemini-3-flash-preview call each judging "same claims,
                       no new facts?" yes/no + note.

Writes outputs/study_b/r7/verify_report.json and prints a markdown summary
to stdout.

Usage:
  .venv/bin/python -m study_b.r7_verify_rewrites [--sample 50] [--seed 202616]
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from pathlib import Path

from study_b.generate_mirrors import MODELS
from study_b.r7_lamp_rewrite import (COPY_NGRAM, COPY_THRESHOLD, OUT, RATIO_HI,
                                     RATIO_LO, SPLITS, TERMINAL_CHARS,
                                     copy_fraction, gemini_api_key,
                                     load_test_mirrors)
JUDGE_MODEL = "gemini-3-flash-preview"

REFUSAL_RE = re.compile(
    r"\b(i can(?:no|')t|i'm sorry|i am sorry|i cannot|as an ai|"
    r"i'm unable|i am unable|i won't be able)\b", re.I)

JUDGE_PROMPT = """\
Compare an ORIGINAL blog post with its REWRITE. The rewrite was supposed to \
change only wording and style. Answer strictly as JSON: \
{"same_claims": "yes"|"no", "note": "<one sentence>"}. \
Say "no" if the rewrite drops a factual claim, number, name, or link from the \
original, or introduces any new fact, figure, example, or claim not in the \
original. Ignore pure phrasing, tone, and sentence-structure changes.

ORIGINAL:
{orig}

REWRITE:
{rew}
"""


def judge_pairs(pairs: list[dict]) -> list[dict]:
    from google import genai
    client = genai.Client(api_key=gemini_api_key())
    out = []
    for p in pairs:
        prompt = (JUDGE_PROMPT
                  .replace("{orig}", p["original_text"])
                  .replace("{rew}", p["rewritten_text"]))
        verdict, note = "judge_error", ""
        for attempt in range(3):
            try:
                r = client.models.generate_content(model=JUDGE_MODEL,
                                                   contents=prompt)
                m = re.search(r'"same_claims"\s*:\s*"(yes|no)"', r.text or "",
                              re.I)
                if m:
                    verdict = m.group(1).lower()
                    nm = re.search(r'"note"\s*:\s*"([^"]*)"', r.text or "")
                    note = nm.group(1) if nm else ""
                    break
                raise ValueError("no verdict in response")
            except Exception as e:
                note = str(e)[:120]
                time.sleep(5 * (attempt + 1))
        out.append({"doc_id": p["doc_id"], "source": p["source"],
                    "same_claims": verdict, "note": note})
    return out


def pct(vals: list[float], q: float) -> float:
    s = sorted(vals)
    return s[min(len(s) - 1, int(q * len(s)))]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="",
                    help="comma list of source keys; default all five")
    ap.add_argument("--sample", type=int, default=50,
                    help="claim-check sample size; 0 = judge every pair")
    ap.add_argument("--seed", type=int, default=202616)
    args = ap.parse_args()

    keys = [k.strip() for k in args.model.split(",") if k.strip()] or list(MODELS)
    splits = json.load(open(SPLITS))
    test_ids = {d for d, s in splits["doc_split"].items() if s == "test"}

    pairs: list[dict] = []
    for key in keys:
        path = OUT / f"rewritten_{key}.jsonl"
        if not path.exists():
            print(f"WARN: {path} missing, skipping {key}", file=sys.stderr)
            continue
        originals = {d["doc_id"]: d for d in load_test_mirrors(key, test_ids)}
        for line in open(path):
            if not line.strip():
                continue
            r = json.loads(line)
            o = originals.get(r["doc_id"])
            if not o:
                print(f"WARN: {key} {r['doc_id']} not in test mirrors",
                      file=sys.stderr)
                continue
            pairs.append({
                "doc_id": r["doc_id"], "source": key,
                "original_text": o["text"],
                "rewritten_text": r["rewritten_text"],
                "usd": r.get("usd", 0.0),
            })
    if not pairs:
        raise SystemExit("no rewrites found under outputs/study_b/r7/")

    # (a) length drift
    ratios, drift_viol = [], []
    for p in pairs:
        ow = len(p["original_text"].split())
        rw = len(p["rewritten_text"].split())
        ratio = rw / max(ow, 1)
        p["ratio"] = round(ratio, 3)
        ratios.append(ratio)
        if not (RATIO_LO <= ratio <= RATIO_HI):
            drift_viol.append({"doc_id": p["doc_id"], "source": p["source"],
                               "ratio": p["ratio"], "orig_words": ow,
                               "rew_words": rw})

    # (b) trivial copy
    copy_flags = []
    for p in pairs:
        frac = copy_fraction(p["original_text"], p["rewritten_text"])
        p["copy_13gram"] = round(frac, 3)
        if frac > COPY_THRESHOLD:
            copy_flags.append({"doc_id": p["doc_id"], "source": p["source"],
                               "copy_13gram": p["copy_13gram"]})

    # (c) refusal / emptiness / truncation
    # truncation heuristic: a rewrite that ends mid-sentence (no terminal
    # punctuation / closing bracket) usually hit the output-token cap
    # (caught live in the pilot: kimi at the old 8k cap).
    refusals = []
    for p in pairs:
        text = p["rewritten_text"].strip()
        head = text[:200]
        truncated = bool(text) and text[-1] not in TERMINAL_CHARS
        if (not text or len(text.split()) < 100 or REFUSAL_RE.search(head)
                or truncated):
            refusals.append({"doc_id": p["doc_id"], "source": p["source"],
                             "words": len(text.split()),
                             "truncated": truncated, "head": head[:120]})

    # (d) claim preservation (LLM judge on a seeded sample)
    rng = random.Random(args.seed)
    if args.sample and args.sample < len(pairs):
        sample = rng.sample(pairs, args.sample)
    else:
        sample = list(pairs)
    print(f"claim-checking {len(sample)} pairs with {JUDGE_MODEL}...",
          file=sys.stderr)
    judgments = judge_pairs(sample)
    n_yes = sum(1 for j in judgments if j["same_claims"] == "yes")
    n_no = sum(1 for j in judgments if j["same_claims"] == "no")
    n_err = len(judgments) - n_yes - n_no

    by_model = {}
    for key in keys:
        kp = [p for p in pairs if p["source"] == key]
        if not kp:
            continue
        by_model[key] = {
            "n": len(kp),
            "ratio_mean": round(sum(p["ratio"] for p in kp) / len(kp), 3),
            "ratio_min": round(min(p["ratio"] for p in kp), 3),
            "ratio_max": round(max(p["ratio"] for p in kp), 3),
            "copy_13gram_mean": round(
                sum(p["copy_13gram"] for p in kp) / len(kp), 3),
            "usd_total": round(sum(p["usd"] for p in kp), 4),
            "usd_per_post": round(sum(p["usd"] for p in kp) / len(kp), 5),
        }

    report = {
        "n_pairs": len(pairs),
        "models": by_model,
        "length_drift": {
            "bounds": [RATIO_LO, RATIO_HI],
            "mean": round(sum(ratios) / len(ratios), 3),
            "p10": round(pct(ratios, 0.10), 3),
            "median": round(pct(ratios, 0.50), 3),
            "p90": round(pct(ratios, 0.90), 3),
            "min": round(min(ratios), 3), "max": round(max(ratios), 3),
            "violations": drift_viol,
        },
        "trivial_copy": {"threshold": COPY_THRESHOLD, "ngram": COPY_NGRAM,
                         "flagged": copy_flags},
        "refusals": refusals,
        "claim_check": {
            "judge_model": JUDGE_MODEL, "seed": args.seed,
            "n_judged": len(judgments), "yes": n_yes, "no": n_no,
            "errors": n_err,
            "preservation_rate": round(n_yes / max(n_yes + n_no, 1), 3),
            "judgments": judgments,
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "verify_report.json", "w") as f:
        json.dump(report, f, indent=2)
    print(f"wrote {OUT / 'verify_report.json'}", file=sys.stderr)

    # markdown summary to stdout
    ld = report["length_drift"]
    cc = report["claim_check"]
    md = [
        "# R7 rewrite verification",
        "",
        f"- pairs verified: **{len(pairs)}**",
        f"- length drift (bounds {RATIO_LO}-{RATIO_HI}): mean {ld['mean']}, "
        f"median {ld['median']}, min {ld['min']}, max {ld['max']}, "
        f"violations **{len(drift_viol)}**",
        f"- trivial-copy flags (>{int(COPY_THRESHOLD*100)}% {COPY_NGRAM}-gram "
        f"overlap): **{len(copy_flags)}**",
        f"- refusals/empty: **{len(refusals)}**",
        f"- claim preservation ({cc['n_judged']} judged, seed {args.seed}): "
        f"**{cc['yes']}/{cc['yes'] + cc['no']} yes** "
        f"(rate {cc['preservation_rate']}, {cc['errors']} judge errors)",
        "",
        "| model | n | ratio mean | ratio min-max | copy mean | $/post |",
        "|---|---|---|---|---|---|",
    ]
    for key, m in by_model.items():
        md.append(f"| {key} | {m['n']} | {m['ratio_mean']} | "
                  f"{m['ratio_min']}-{m['ratio_max']} | "
                  f"{m['copy_13gram_mean']} | {m['usd_per_post']} |")
    print("\n".join(md))

    gates_pass = not drift_viol and not copy_flags and not refusals
    return 0 if gates_pass else 1


if __name__ == "__main__":
    sys.exit(main())
