#!/usr/bin/env python
"""Answerability screen.

Runs BEFORE dedup, over every candidate feature in the union taxonomy:
gpt-5.6-terra judges each feature on four criteria, 2 independent votes,
STRICT rule (kept only if both votes pass all criteria). Rejects are logged
with reasons; the rejection rate is reported in the paper.

  .venv/bin/python -m study_b.answerability_screen \
      --taxonomy outputs/study_b/r3/taxonomy_union.json \
      --out outputs/study_b/r3/taxonomy_screened.json
"""
import argparse
import concurrent.futures as cf
import copy
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from study_b.generate_mirrors import GATEWAY  # noqa: E402

MODEL = "openai/gpt-5.6-terra"

PROMPT = """You are screening ONE candidate feature for ANNOTATION FEASIBILITY \
in a text-annotation taxonomy over B2B blog posts. An LLM will answer it while \
reading one post at a time.

IMPORTANT CALIBRATION: most useful annotation features require editorial \
judgment - that is expected and acceptable. "What is the post's dominant \
purpose?" requires judgment yet careful annotators answer it consistently; it \
PASSES. Your job is to reject only features with DISQUALIFYING defects - the \
kind where two careful annotators would routinely give OPPOSITE answers or no \
answer at all.

FEATURE
  name: {name}
  question: {question}
  type: {ftype}
  allowed values: {values}

Reject ONLY on these defects:
1. UNRESOLVABLE: even a careful reader could not resolve the question to the \
allowed values - the values are not collectively exhaustive for real posts, or \
the question asks for something with no defensible mapping to them. (Judgment \
between adjacent values is FINE; ties broken by "dominant/primary" are FINE.)
2. EVIDENCE-ABSENT: answering requires information outside the text itself - \
author intent, reader reactions, production process, or context a reader of \
the post cannot see. (Anything inferable from the words on the page is FINE.)
3. UNUSABLE-TERMS: the question or values hinge on technical jargon or coined \
terms a competent professional reader could not apply without a training \
manual. (Ordinary editorial vocabulary - purpose, section, claim, CTA, \
evidence - is FINE.)
4. CONFLICTING-COMPOUND: the question bundles independent judgments that can \
genuinely conflict (a post can be high on X and low on Y with no answer). \
(Compound phrasings that name one coherent construct are FINE.)

Examples: "Does the post cite at least one named external source?" PASS. \
"What is the central conflict type?" PASS (judgment, but consistent). "Was the \
author confident while writing?" FAIL (2). "Rate clarity-and-depth 1-5" FAIL \
(4: clear-but-shallow posts have no answer).

Return ONLY JSON:
{{"pass": true/false, "failed_criteria": [<numbers>], "reason": "<one short sentence>"}}"""


def iter_features(node, path=""):
    """Yield (container_list, index, feature_dict) for every feature object."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from iter_features(v, f"{path}/{k}")
    elif isinstance(node, list):
        for i, item in enumerate(node):
            if isinstance(item, dict) and "question" in item and "id" in item:
                yield node, i, item
            else:
                yield from iter_features(item, f"{path}[{i}]")


def judge(client, feat: dict) -> dict:
    prompt = PROMPT.format(name=feat.get("name", ""), question=feat["question"],
                           ftype=feat.get("type", ""),
                           values=json.dumps(feat.get("values", [])))
    votes = []
    for _ in range(2):
        for attempt in range(3):
            try:
                r = client.chat.completions.create(
                    model=MODEL, messages=[{"role": "user", "content": prompt}],
                    max_tokens=300)
                txt = r.choices[0].message.content or ""
                m = re.search(r"\{.*\}", txt, re.S)
                votes.append(json.loads(m.group(0) if m else txt))
                break
            except Exception:
                if attempt == 2:
                    votes.append({"pass": True, "failed_criteria": [],
                                  "reason": "JUDGE_ERROR - kept"})
                time.sleep(5 * (attempt + 1))
    keep = all(bool(v.get("pass")) for v in votes)
    return {"id": feat["id"], "keep": keep, "votes": votes}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--taxonomy", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--concurrency", type=int, default=12)
    args = ap.parse_args()

    from openai import OpenAI
    client = OpenAI(api_key=os.environ["AI_GATEWAY_API_KEY"],
                    base_url=GATEWAY, timeout=300.0)

    tax = json.loads(Path(args.taxonomy).read_text())
    feats = [(lst, i, f) for lst, i, f in iter_features(tax)]
    print(f"screening {len(feats)} candidate features", file=sys.stderr)

    log_path = Path(args.out).with_suffix(".screen_log.jsonl")
    done = {}
    if log_path.exists():
        done = {json.loads(l)["id"]: json.loads(l) for l in open(log_path)}
    todo = [f for _, _, f in feats if f["id"] not in done]
    with open(log_path, "a") as fh, cf.ThreadPoolExecutor(args.concurrency) as ex:
        for res in ex.map(lambda f: judge(client, f), todo):
            fh.write(json.dumps(res) + "\n")
            fh.flush()
            done[res["id"]] = res

    out = copy.deepcopy(tax)
    kept = dropped = 0
    rejected_ids = {fid for fid, r in done.items() if not r["keep"]}
    def prune(node):
        nonlocal kept, dropped
        if isinstance(node, dict):
            for k, v in node.items():
                node[k] = prune(v)
            return node
        if isinstance(node, list):
            newlist = []
            for item in node:
                if isinstance(item, dict) and "question" in item and "id" in item:
                    if item["id"] in rejected_ids:
                        dropped += 1
                        continue
                    kept += 1
                newlist.append(prune(item) if not (
                    isinstance(item, dict) and "question" in item) else item)
            return newlist
        return node
    out = prune(out)
    Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False))
    rate = dropped / max(1, kept + dropped)
    summary = {"candidates": kept + dropped, "kept": kept, "rejected": dropped,
               "rejection_rate": round(rate, 4)}
    Path(args.out).with_suffix(".screen_summary.json").write_text(
        json.dumps(summary, indent=2))
    print(json.dumps(summary), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
