#!/usr/bin/env python
"""T0: B2B template-schema discovery.

Derives a B2B-native template schema from REAL human posts before stage 2.
Three independent gpt-5.6-terra discovery runs over ~40 stratified
spot-check-verified posts -> consolidation -> NarraBench mapping table.
Human posts only (blinding: the schema never sees AI text).

Outputs (durable + committed on PI freeze):
  outputs/study_b/t0/input_posts.jsonl      the sampled posts (provenance)
  outputs/study_b/t0/discovery_run{1,2,3}.md
  outputs/study_b/t0/SCHEMA_PROPOSAL.md     consolidated schema + mapping
Gates: 8-12 dimensions; >=2 GLOBAL + >=1 LOCAL field each;
PI review freezes artifacts/TEMPLATE_SCHEMA_V2.md before any stage-2 spend.

  .venv/bin/python -m study_b.t0_schema_discovery [--n-posts 40]
"""
import argparse
import csv
import json
import os
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests
import trafilatura

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

OUT = Path("outputs/study_b/t0")
GATEWAY = "https://ai-gateway.vercel.sh/v1"
MODEL = "openai/gpt-5.6-terra"
SEED = 202608
UA = {"User-Agent": "sitefire-slop-benchmark/0.1 (research; jochen@sitefire.ai)"}

NARRABENCH = ("Agent, Social Network, Event, Plot, Structure, Setting, Time, "
              "Revelation, Perspective, Style")

DISCOVER_PROMPT = """You are a discourse analyst. Below are {n} real, human-written \
B2B blog posts (published 2009-2022) from companies across software, fintech, \
health, e-commerce, devtools, edtech and services.

TASK: induce, bottom-up, the STRUCTURAL DIMENSIONS along which such posts vary - \
the discourse-level architecture of B2B informational content. Think: what are \
the load-bearing structural elements of these posts, analogous to how narrative \
theory decomposes fiction into plot, agents, temporal structure, etc.?

Rules:
- Discourse-level structure only, NOT surface style (no diction/rhythm/tone \
dimensions except at most ONE consolidated Style bucket).
- Each dimension must be OBSERVABLE in a single post and describable through \
concrete fields (things an annotator could extract or answer).
- 8-12 dimensions. For each: name, one-sentence definition, 3-6 concrete \
sub-aspects (fields) with GLOBAL (whole-post) or LOCAL (per-section) scope.
- Ground every dimension in evidence: cite 2-3 post numbers exhibiting variation \
on it.

Return markdown: one section per dimension with the fields listed.

THE {n} POSTS:
{posts}"""

CONSOLIDATE_PROMPT = """Three independent analysts each proposed structural \
dimension systems for human-written B2B blog posts. Consolidate them into ONE \
schema of 8-12 dimensions:
- Merge synonymous dimensions (keep the clearest name/definition).
- Keep a dimension only if >=2 analysts found it OR one analyst grounded it in \
strong evidence.
- Each dimension: name, definition, 3-6 fields with [GLOBAL] or [LOCAL] scope, \
each field with an extraction-ready one-line description. Minimum 2 GLOBAL and \
1 LOCAL field per dimension.
- At most ONE Style dimension (sentence/phrase-level texture), mirroring the \
role style plays in NarraBench.

Then add a MAPPING TABLE against the NarraBench narrative dimensions \
({narrabench}): for each NarraBench dimension state KEPT (transfers as-is, \
under which name), ADAPTED (renamed/reworked into which of yours), REPLACED \
(fiction-specific; superseded by which of yours), or DROPPED (no B2B analogue) \
- one line of rationale each.

Finally: emit the machine schema as a JSON block mapping dimension_key -> \
{{"definition": str, "fields": [{{"name": str, "scope": "GLOBAL|LOCAL", \
"description": str}}]}}.

ANALYST 1:
{run1}

ANALYST 2:
{run2}

ANALYST 3:
{run3}"""


def sample_posts(n: int) -> list[dict]:
    dl = {r["domain"]: r for r in csv.DictReader(
        open("outputs/study_b/spotcheck/decision_list.csv"))}
    kept = {r["domain"] for r in csv.DictReader(
        open("outputs/study_b/spotcheck/decision_list_kept.csv"))}
    posts = [r for r in csv.DictReader(open("outputs/study_b/spotcheck/posts.csv"))
             if r["usable"] in ("True", "1", "true") and r["domain"] in kept]
    by_vert = defaultdict(list)
    for p in posts:
        by_vert[dl.get(p["domain"], {}).get("vertical", "services_other")].append(p)
    rng = random.Random(SEED)
    order = sorted(by_vert)  # deterministic
    picked, used_domains = [], set()
    while len(picked) < n and any(by_vert.values()):
        for v in order:
            pool = [p for p in by_vert[v] if p["domain"] not in used_domains]
            if not pool:
                pool = by_vert[v]
            if pool and len(picked) < n:
                p = rng.choice(pool)
                by_vert[v].remove(p)
                used_domains.add(p["domain"])
                picked.append(p)
    return picked


def fetch_text(p: dict) -> str | None:
    try:
        r = requests.get(
            f"https://web.archive.org/web/{p['snapshot_ts']}id_/{p['url']}",
            headers=UA, timeout=60)
        time.sleep(2.5)
        if r.status_code != 200:
            return None
        doc = trafilatura.bare_extraction(r.content, include_comments=False,
                                          with_metadata=True)
        return doc.text if doc and doc.text else None
    except Exception:
        return None


def llm(client, prompt: str, max_tokens: int = 8000) -> str:
    for attempt in range(3):
        try:
            r = client.chat.completions.create(
                model=MODEL, messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens)
            return r.choices[0].message.content or ""
        except Exception:
            time.sleep(10 * (attempt + 1))
    raise RuntimeError("terra call failed 3x")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-posts", type=int, default=40)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    inp = OUT / "input_posts.jsonl"
    if not inp.exists():
        picked = sample_posts(args.n_posts * 2)  # oversample; some fetches fail
        got = []
        with open(inp, "w") as fh:
            for p in picked:
                if len(got) >= args.n_posts:
                    break
                text = fetch_text(p)
                if text and len(text.split()) >= 400:
                    rec = {"domain": p["domain"], "url": p["url"],
                           "ts": p["snapshot_ts"], "title": p["title"],
                           "text": text}
                    fh.write(json.dumps(rec) + "\n")
                    got.append(rec)
                    print(f"  [{len(got)}/{args.n_posts}] {p['domain']}",
                          file=sys.stderr)
        print(f"input: {len(got)} posts", file=sys.stderr)

    posts = [json.loads(l) for l in open(inp)]
    blob = "\n\n".join(
        f"=== POST {i+1} ({p['domain']}) ===\nTITLE: {p['title']}\n"
        + " ".join(p["text"].split()[:1100])
        for i, p in enumerate(posts))

    from openai import OpenAI
    client = OpenAI(api_key=os.environ["AI_GATEWAY_API_KEY"],
                    base_url=GATEWAY, timeout=900.0)

    runs = []
    for i in (1, 2, 3):
        f = OUT / f"discovery_run{i}.md"
        if f.exists():
            runs.append(f.read_text())
            continue
        print(f"discovery run {i}...", file=sys.stderr)
        out = llm(client, DISCOVER_PROMPT.format(n=len(posts), posts=blob))
        f.write_text(out)
        runs.append(out)

    print("consolidating...", file=sys.stderr)
    cons = llm(client, CONSOLIDATE_PROMPT.format(
        narrabench=NARRABENCH, run1=runs[0], run2=runs[1], run3=runs[2]),
        max_tokens=12000)
    (OUT / "SCHEMA_PROPOSAL.md").write_text(cons)
    print(f"wrote {OUT/'SCHEMA_PROPOSAL.md'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
