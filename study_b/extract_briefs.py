"""M3: brief extraction - one neutral content brief per frozen human post.

Mirrors the paper's prompt reverse-engineering step (they inferred a writing
prompt from each human story with Gemini Flash; we infer a content BRIEF from
each human blog post). The brief is the shared "assignment" all seven sources
write from - the parallel-corpus control. Constraints enforced by the prompt:
the brief describes the assignment (topic, audience, angle, format, length),
and must NOT quote or closely paraphrase distinctive wording of the original.

Resume-safe: briefs stream to briefs.jsonl keyed by doc_id; rerunning skips
existing docs. Cost cap guard identical to the corpus fetcher.

Usage:
  .venv/bin/python -m study_b.extract_briefs [--limit N] [--concurrency 4]
      [--model gemini-3-flash-preview] [--max-llm-calls 5000]

Output: outputs/study_b/corpus/briefs.jsonl  (doc_id, brief fields, model)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

CORPUS = Path("outputs/study_b/corpus/story_human_frozen.parquet")
OUT = Path("outputs/study_b/corpus/briefs_v2.jsonl")   # v1 briefs.jsonl is
# retained untouched as the confounded baseline for the paired comparison

# v2 (2026-07-27). Clause-by-clause adaptation of the paper's Figure 6, which
# REQUIRES source-specific naming ("introduce at least one key character or
# setting by name"). v1 forbade naming the publisher, which is the opposite, and
# that deviation caused the commercial-layer confound: human
# posts carried a commercial layer the AI was never asked to produce.
#
# On a company blog the publisher IS the protagonist. v2 restores it, and also
# restores the paper's OUTPUT SHAPE - one prose paragraph <=120 words, not a
# structured form, since a form-shaped prompt plausibly induces the mechanical
# uniformity we are trying to measure.
#
# Only "prompt" is ever sent to a writer. "meta" is analysis-only: passing
# commercial_goal would install the CTA we want to observe, and passing
# first_hand_sources would induce quote fabrication. Anything we want to MEASURE
# must not be something we TOLD it.
BRIEF_PROMPT = """You are a content strategist generating **writing briefs** \
for published B2B blog posts. For the post below, craft one brief that:
1. Begins with **"Write a blog post"** (exact phrase).
2. Continue with **"for..."** and name the publishing company and what it \
sells, then continue with **"about...", "explaining...", or "arguing that..."** \
and state what the post is about. This keeps the opening grammatically smooth \
and keeps the publisher the commissioner of the post rather than its subject.
- If the publisher's name does not appear in the text, refer to it as "the \
publisher" without inventing a name. Otherwise, provide the company name \
explicitly.
3. Conveys the post's distinctive **essence / angle / style**, giving the \
writer a clear sense of register and direction, and includes **some concrete \
details** (the reader's problem, the product category, the decision at stake) \
as needed - don't overload with minutiae.
4. Offers enough editorial guidance to get the writer started (the reader's \
situation + the question the post resolves) yet leaves room for their own \
treatment.
5. Do **not** address the reader in second person; keep the brief in \
third-person imperative (no "you/your").
6. Avoid vague hedge words (*maybe*, *perhaps*, *consider*) **and** absolutely \
do NOT use comparison phrases or qualifiers such as *like*, *much like*, \
*similar to*, *reminiscent of*, *in the style of*. Refer to the concrete names \
/ details directly. Do not invent company, product, or person names that do \
not appear.
7. Do NOT quote or closely paraphrase distinctive sentences, statistics, or \
anecdotes. A writer working only from this brief must not be able to \
reconstruct its wording.
8. Single paragraph <= 120 words.

Return ONLY the brief text - no extra commentary.

POST TITLE: {title}

POST TEXT:
{text}
"""

# SECOND, SEPARATE call. Analysis-only labels; never shown to any writer and
# never used to condition the brief. Split from BRIEF_PROMPT deliberately: one
# completion producing both would condition the brief on the commercial goal,
# which is the contamination we rejected candidate B for.
META_PROMPT = """Label this published B2B blog post for a research corpus. \
Report only what the post itself evidences.

Return ONLY a JSON object:
{"publisher": "<company name, or 'unnamed'>",
 "format": "<how_to | guide | listicle | comparison | explainer>",
 "commercial_goal": "<demo | signup | resource_download | awareness_only>",
 "first_hand_sources": ["<customer_interview | proprietary_data | in_house_expertise | none>"]}

POST TITLE: {title}

POST TEXT:
{text}
"""


def make_client(model: str):
    from google import genai

    key = next((os.environ[v] for v in
                [f"GEMINI_API_KEY_{i}" for i in range(1, 8)]
                + ["GEMINI_API_KEY"] if os.environ.get(v)), None)
    if not key:
        raise SystemExit("no GEMINI_API_KEY_* in environment; source .env")
    return genai.Client(api_key=key), model


def normalize_brief(brief: dict) -> dict:
    """Two fixes found in the v2 pilot (2026-07-27).

    1. Enum drift: the model returned `in-house_expertise` for one doc and
       `in_house_expertise` for others. Left alone, stratifying on
       `first_hand_sources` would silently split one category into two.
    2. Em-dashes in the brief paragraph. Briefs reach only the AI sources (the
       human never saw one), so any punctuation habit the brief carries is an
       asymmetry we introduced. Cheap to remove, so remove it.
    """
    enum = lambda v: str(v).strip().lower().replace("-", "_").replace(" ", "_")
    m = brief.get("meta") or {}
    for k in ("format", "commercial_goal"):
        if m.get(k) is not None:
            m[k] = enum(m[k])
    fhs = m.get("first_hand_sources")
    if isinstance(fhs, str):
        fhs = [fhs]
    if isinstance(fhs, list):
        m["first_hand_sources"] = sorted({enum(x) for x in fhs if str(x).strip()})
    for dash in ("—", "–"):
        brief["prompt"] = brief["prompt"].replace(dash, " - ")
    brief["prompt"] = " ".join(brief["prompt"].split())
    return brief


def _call(client, model: str, prompt: str, row) -> str | None:
    filled = (prompt.replace("{title}", str(row.title)[:200])
                    .replace("{text}", " ".join(str(row.story_human).split()[:1800])))
    for attempt in range(3):
        try:
            return client.models.generate_content(model=model,
                                                  contents=filled).text
        except Exception:
            time.sleep(4 * (attempt + 1))
    return None


def extract_one(client, model: str, row) -> dict | None:
    # PASS 1 - the writer-facing brief. Prose only, exactly as the paper's
    # Figure 6 returns prose only.
    text = _call(client, model, BRIEF_PROMPT, row)
    if not text or not text.strip():
        return None
    prompt = " ".join(text.strip().split())
    if prompt.count(" ") < 20:            # degenerate / refusal
        return None

    # PASS 2 - analysis-only labels, from the POST, not from the brief.
    meta = {}
    raw = _call(client, model, META_PROMPT, row)
    if raw:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                meta = json.loads(m.group(0))
            except Exception:
                meta = {}
    # target length comes from the actual post, not the model's guess
    meta["target_words"] = int(round(row.words / 100.0) * 100) or 100

    brief = normalize_brief({"prompt": prompt, "meta": meta})
    return {"doc_id": row.doc_id, "domain": row.domain,
            "stratum": row.stratum, "vertical": row.vertical,
            "brief": brief, "model": model}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--model", default="gemini-3-flash-preview")
    parser.add_argument("--max-llm-calls", type=int, default=5000)
    parser.add_argument("--out", default=str(OUT),
                        help="brief output path (default: v2)")
    parser.add_argument("--doc-ids", default="",
                        help="comma-separated doc_ids, or a file of them; "
                             "restricts extraction to those docs")
    args = parser.parse_args()

    import pandas as pd

    out_path = Path(args.out)
    corpus = pd.read_parquet(CORPUS)
    if args.doc_ids:
        raw = (Path(args.doc_ids).read_text() if Path(args.doc_ids).exists()
               else args.doc_ids)
        keep = {x.strip() for x in raw.replace("\n", ",").split(",") if x.strip()}
        corpus = corpus[corpus.doc_id.isin(keep)]
        print(f"restricted to {len(corpus)} of {len(keep)} requested doc_ids",
              file=sys.stderr)
    done: set[str] = set()
    if out_path.exists():
        done = {json.loads(l)["doc_id"] for l in open(out_path) if l.strip()}
    todo = corpus[~corpus.doc_id.isin(done)]
    if args.limit:
        todo = todo.head(args.limit)
    print(f"briefs: {len(todo)} to extract ({len(done)} done)", file=sys.stderr)
    if not len(todo):
        return 0

    client, model = make_client(args.model)
    n_calls, n_ok, n_fail = 0, 0, 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    f = open(out_path, "a")
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = {ex.submit(extract_one, client, model, row): row.doc_id
                   for row in todo.itertuples()}
        for fut in as_completed(futures):
            n_calls += 1
            if n_calls > args.max_llm_calls:
                print("FATAL: LLM cap exceeded", file=sys.stderr)
                return 2
            res = fut.result()
            if res:
                f.write(json.dumps(res) + "\n")
                n_ok += 1
                if n_ok % 100 == 0:
                    f.flush()
                    print(f"[{n_ok+n_fail}/{len(todo)}] {n_ok} ok",
                          file=sys.stderr)
            else:
                n_fail += 1
    f.close()
    print(f"done: {n_ok} briefs, {n_fail} failed (rerun to retry failures)",
          file=sys.stderr)
    return 0 if n_fail < len(todo) * 0.05 else 1


if __name__ == "__main__":
    sys.exit(main())
