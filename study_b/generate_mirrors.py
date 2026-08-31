"""M4: generate AI mirror articles - five models write from every brief.

Replicates the paper's stage 1 (story generation) for nonfiction:
  - the paper's five models, unchanged (see artifacts/REPLICATION_CONTRACT.md)
  - an explicit "approximately N words" instruction, as in their Figure 7
  - NO temperature/top_p override: their API providers use provider defaults
  - generous max_tokens, as in their story_generation stage config

All five route through the Vercel AI Gateway (OpenAI-compatible). This is a
plumbing choice, not a methodology one: one interface means identical
parameter handling and one usage/latency accounting path across models,
which is a tighter control than the paper's per-provider SDKs.

Resume-safe: each model streams to its own JSONL keyed by doc_id; rerunning
skips completed docs. Per-generation latency, tokens and retry counts are
recorded so overnight scheduling can be planned from measurements.

Usage:
  .venv/bin/python -m study_b.generate_mirrors --smoke 2
  .venv/bin/python -m study_b.generate_mirrors [--models gpt,claude] [--limit N]
      [--concurrency 4] [--max-usd 250]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

CORPUS_BRIEFS = Path("outputs/study_b/corpus/briefs.jsonl")
OUT = Path("outputs/study_b/mirrors")
GATEWAY = "https://ai-gateway.vercel.sh/v1"

# The paper's five generation models (artifacts/REPLICATION_CONTRACT.md).
# usd per 1M tokens (input, output) - from the gateway catalogue 2026-07-24.
MODELS = {
    "gpt":      ("openai/gpt-5.4",              2.50, 15.00),
    "claude":   ("anthropic/claude-sonnet-4.6", 3.00, 15.00),
    "gemini":   ("google/gemini-3-flash",       0.50,  3.00),
    "deepseek": ("deepseek/deepseek-v3.2",      0.28,  0.42),
    "kimi":     ("moonshotai/kimi-k2.5",        0.60,  3.00),
}

# Nonfiction counterpart of their SYSTEM_PROMPT ("You are a creative writing
# expert who generates rich, detailed stories."). No humanization coaching:
# we measure default model behavior.
SYSTEM_PROMPT = ("You are an expert content writer who produces rich, "
                 "detailed articles.")


def target_words(brief: dict) -> int:
    """v2 keeps target_words inside `meta`; v1 has it at the top level."""
    if "meta" in brief:
        return int((brief.get("meta") or {}).get("target_words") or 1000)
    return int(brief["target_words"])


def build_prompt(brief: dict) -> str:
    """Render the writer-facing prompt. Paper parity: ONE prose paragraph plus
    the word-count sentence, exactly as their Figure 7.

    v2 briefs carry {"prompt", "meta"}; `meta` is analysis-only and must NEVER
    reach a generator - passing commercial_goal would install the
    CTA we want to observe, and passing first_hand_sources would induce quote
    fabrication. v1 briefs (flat topic/audience/angle fields) are still rendered
    for the paired comparison against the confounded baseline.
    """
    if "prompt" in brief:                                    # v2
        target = target_words(brief)
        body = str(brief["prompt"]).strip()
    else:                                                    # v1, legacy
        kq = brief.get("key_questions") or []
        target = target_words(brief)
        lines = [f"Topic: {brief['topic']}", f"Audience: {brief['audience']}",
                 f"Angle: {brief['angle']}", f"Format: {brief['format']}"]
        if kq:
            lines.append("Questions the article should answer:")
            lines += [f"- {q}" for q in kq]
        body = "\n".join(lines)
    # mirrors their Figure 7 phrasing: "must be approximately N words long"
    return (f"{body}\n\nYour article must be approximately {target} words long."
            f"\nWrite only the article, beginning with a title line.")


def gateway_balance() -> float | None:
    """Remaining AI Gateway credit in USD, or None if unavailable."""
    import requests
    try:
        r = requests.get(f"{GATEWAY}/credits", timeout=20,
                         headers={"Authorization":
                                  f"Bearer {os.environ['AI_GATEWAY_API_KEY']}"})
        r.raise_for_status()
        return float(r.json()["balance"])
    except Exception as e:
        print(f"WARN: could not read gateway balance: {str(e)[:70]}",
              file=sys.stderr)
        return None


# measured $/article from the 2026-07-24 smoke test (10 generations)
COST_PER_ARTICLE = {"gpt": 0.0276, "claude": 0.0256, "gemini": 0.0077,
                    "deepseek": 0.0007, "kimi": 0.0068}


class Runner:
    def __init__(self, max_usd: float):
        from openai import OpenAI

        key = os.environ.get("AI_GATEWAY_API_KEY")
        if not key:
            raise SystemExit("AI_GATEWAY_API_KEY missing; source .env")
        self.client = OpenAI(api_key=key, base_url=GATEWAY, timeout=600.0)
        self.max_usd = max_usd
        self.spent = 0.0
        self.lock = Lock()

    def generate(self, key: str, brief_row: dict) -> dict | None:
        model_id, pin, pout = MODELS[key]
        prompt = build_prompt(brief_row["brief"])
        retries = 0
        for attempt in range(4):
            with self.lock:
                if self.spent >= self.max_usd:
                    return {"_capped": True}
            t0 = time.time()
            try:
                r = self.client.chat.completions.create(
                    model=model_id,
                    messages=[{"role": "system", "content": SYSTEM_PROMPT},
                              {"role": "user", "content": prompt}],
                    max_tokens=8000,   # generous, as in their stage config
                )
                dt = time.time() - t0
                text = r.choices[0].message.content or ""
                if len(text.split()) < 100:      # degenerate output
                    raise ValueError(f"short output ({len(text.split())} words)")
                u = r.usage
                cost = (u.prompt_tokens / 1e6) * pin + (u.completion_tokens / 1e6) * pout
                rt = getattr(u, "completion_tokens_details", None)
                reasoning = getattr(rt, "reasoning_tokens", 0) if rt else 0
                with self.lock:
                    self.spent += cost
                return {
                    "doc_id": brief_row["doc_id"], "source": key,
                    "model_id": model_id, "domain": brief_row["domain"],
                    "stratum": brief_row["stratum"],
                    "vertical": brief_row["vertical"],
                    "target_words": target_words(brief_row["brief"]),
                    "text": text, "words": len(text.split()),
                    "in_tokens": u.prompt_tokens, "out_tokens": u.completion_tokens,
                    "reasoning_tokens": reasoning, "usd": round(cost, 5),
                    "latency_s": round(dt, 2), "retries": retries,
                }
            except Exception as e:
                retries += 1
                if attempt == 3:
                    print(f"  FAIL {key} {brief_row['doc_id']}: {str(e)[:90]}",
                          file=sys.stderr)
                    return None
                time.sleep(5 * (attempt + 1))
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--models", default="", help="comma list; default all five")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--smoke", type=int, default=0,
                    help="generate N briefs per model into a smoke/ dir")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--max-usd", type=float, default=250.0)
    ap.add_argument("--briefs", default=str(CORPUS_BRIEFS),
                    help="brief jsonl (default: v1 baseline)")
    ap.add_argument("--outdir", default="",
                    help="mirror output dir (default: outputs/study_b/mirrors)")
    ap.add_argument("--ignore-balance", action="store_true",
                    help="skip the credit preflight (not recommended)")
    args = ap.parse_args()

    keys = [k.strip() for k in args.models.split(",") if k.strip()] or list(MODELS)
    for k in keys:
        if k not in MODELS:
            raise SystemExit(f"unknown model key {k}; have {list(MODELS)}")

    briefs = [json.loads(l) for l in open(args.briefs) if l.strip()]
    outdir = (Path(args.outdir) if args.outdir
              else (OUT / "smoke" if args.smoke else OUT))
    outdir.mkdir(parents=True, exist_ok=True)
    if args.smoke:
        briefs = briefs[:args.smoke]
    elif args.limit:
        briefs = briefs[:args.limit]

    # PREFLIGHT: refuse to start a run the credit balance cannot finish.
    # (Learned 2026-07-24: balance was $44.85 against a $156 batch - would
    # have died ~29% in, overnight, with no operator awake.)
    projected = sum(COST_PER_ARTICLE[k] * len(briefs) for k in keys)
    bal = gateway_balance()
    if bal is not None:
        print(f"gateway balance ${bal:.2f} | projected need ${projected:.2f}",
              file=sys.stderr)
        if bal < projected * 1.15 and not args.ignore_balance:
            print(f"\nABORT: insufficient gateway credit. Need ~${projected:.2f} "
                  f"(+15% headroom = ${projected*1.15:.2f}), have ${bal:.2f}.\n"
                  f"Top up at https://vercel.com/dashboard -> AI Gateway -> "
                  f"Credits, or rerun with --ignore-balance to proceed anyway.",
                  file=sys.stderr)
            return 3

    runner = Runner(args.max_usd)
    grand_total = 0
    for key in keys:
        path = outdir / f"story_{key}.jsonl"
        done = set()
        if path.exists():
            done = {json.loads(l)["doc_id"] for l in open(path) if l.strip()}
        todo = [b for b in briefs if b["doc_id"] not in done]
        print(f"\n=== {key} ({MODELS[key][0]}): {len(todo)} to generate "
              f"({len(done)} done) ===", file=sys.stderr)
        if not todo:
            continue
        f = open(path, "a")
        n_ok = n_fail = 0
        capped = False
        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            futs = {ex.submit(runner.generate, key, b): b["doc_id"] for b in todo}
            for fut in as_completed(futs):
                res = fut.result()
                if res and res.get("_capped"):
                    capped = True
                    continue
                if res:
                    f.write(json.dumps(res) + "\n")
                    n_ok += 1
                    if n_ok % 25 == 0:
                        f.flush()
                        print(f"  [{n_ok + n_fail}/{len(todo)}] ok={n_ok} "
                              f"spent=${runner.spent:.2f}", file=sys.stderr)
                else:
                    n_fail += 1
        f.close()
        grand_total += n_ok
        print(f"  {key}: {n_ok} ok, {n_fail} failed, "
              f"running spend ${runner.spent:.2f}", file=sys.stderr)
        if capped:
            print(f"STOPPED: spend cap ${args.max_usd} reached", file=sys.stderr)
            return 2

    print(f"\ntotal generated this run: {grand_total}; "
          f"spend ${runner.spent:.2f}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
