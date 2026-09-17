"""R7: LAMP rewording-durability attack - each model rewrites ITS OWN posts.

Rewrites the 1,450 test-split AI mirrors (290 prompts x 5 models) with a
span-level edit prompt targeting the seven LAMP artifact categories
(Chakrabarty et al. 2025, arXiv 2409.14509; see prompts/lamp_rewrite.md and
the original study's section 8.3). Self-rewrite by design: the
original paper tested only Gemini-rewrites-Gemini; we run all five sources.

The prompt says nothing about document structure in either direction - the
attack is the natural LAMP-style edit, neither protecting nor targeting
structure, which is what keeps the durability test fair.

Provider routing (model IDs pinned, not guessed):
  gpt      -> OpenAI direct,   gpt-5.4              (as study_b/style_audit.py)
  claude   -> Anthropic direct, claude-sonnet-4-6   (resolved via /v1/models;
              native id of the gateway's anthropic/claude-sonnet-4.6)
  gemini   -> Google GenAI,    gemini-3-flash-preview (AI Studio id of the
              gateway's google/gemini-3-flash; plain gemini-3-flash 404s
              natively - verified 2026-08-30. Key rotation as spot_check.py)
  deepseek -> Vercel AI Gateway, deepseek/deepseek-v3.2
  kimi     -> Vercel AI Gateway, moonshotai/kimi-k2.5

Retry/rate-limit handling mirrors study_b/generate_mirrors.py: 4 attempts,
linear backoff 5*(attempt+1)s, degenerate-output guard, resume-safe JSONL
keyed by doc_id, modest thread concurrency.

Usage:
  .venv/bin/python -m study_b.r7_lamp_rewrite --pilot 2
  .venv/bin/python -m study_b.r7_lamp_rewrite [--model gpt,claude]
      [--concurrency 4] [--max-usd 100]
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

# reuse the mirror config verbatim: gateway ids + $/1M (input, output)
from study_b.generate_mirrors import GATEWAY, MODELS

SPLITS = Path("outputs/study_b/r6/splits.json")
MIRRORS = Path("outputs/study_b/mirrors")
OUT = Path("outputs/study_b/r7")
PROMPT_FILE = Path("prompts/lamp_rewrite.md")

# native model ids for the three direct-API sources; deepseek/kimi keep the
# gateway id from MODELS.
NATIVE_ID = {
    "gpt": "gpt-5.4",
    "claude": "claude-sonnet-4-6",
    "gemini": "gemini-3-flash-preview",
}

# 16000, not generate_mirrors' 8000: kimi-k2.5 spent 7,037 reasoning tokens
# on a pilot rewrite and truncated the visible text at the 8000 cap
# (2026-08-30). Reasoning models need the headroom.
MAX_OUT_TOKENS = 16000

# Same pattern as generate_mirrors.SYSTEM_PROMPT (a role-setting system
# message for every provider). Load-bearing for deepseek-v3.2: without a
# system message it returns the post verbatim (13-gram copy fraction 0.98-1.0
# across three prompt variants); with it, 0.011 (probed 2026-08-30).
SYSTEM_PROMPT = ("You are a meticulous line editor. You rewrite flawed spans "
                 "of prose in fresh wording while preserving all facts.")

# In-loop trivial-copy guard: deepseek-v3.2 no-ops the edit nondeterministically
# even with the system message (pilot: 1 of 2 rewrites came back verbatim).
# A near-verbatim response is treated like a degenerate output and retried.
COPY_NGRAM, COPY_THRESHOLD = 13, 0.90

# Full-run robustness guards (added after the first 1,450-post pass;
# both mirror gates the verifier already enforces, so a failing output is
# retried in-loop instead of surfacing as a post-hoc gate violation):
# - TERMINAL_CHARS: a rewrite that ends on none of these characters was cut
#   off mid-sentence (kimi-k2.5 hit the 16k cap 3/290 times when hidden
#   reasoning ran to ~14-16k tokens). Includes the unicode curly quotes -
#   the straight-quote-only set false-flagged one legitimate gpt rewrite
#   ending on a curly close-quote. Shared with r7_verify_rewrites.
# - RATIO_LO/HI: the verifier's length-drift bounds; deepseek once returned
#   a 176-word summary of a 1,210-word post (0.145 ratio) that passed the
#   100-word degenerate check, and gemini condensed 4/290 posts below 0.6.
TERMINAL_CHARS = ".!?\"')]}*`|:”’"
RATIO_LO, RATIO_HI = 0.6, 1.4


def copy_fraction(orig: str, rew: str, n: int = COPY_NGRAM) -> float:
    """Fraction of the rewrite's word n-grams already present in the original.
    1.0 = verbatim copy / no real edit. Shared with r7_verify_rewrites."""
    ow, rw = orig.lower().split(), rew.lower().split()
    rgrams = {tuple(rw[i:i + n]) for i in range(len(rw) - n + 1)}
    if not rgrams:
        return 1.0  # too short to have any n-grams: treat as no real edit
    ograms = {tuple(ow[i:i + n]) for i in range(len(ow) - n + 1)}
    return len(rgrams & ograms) / len(rgrams)


def load_prompt_template() -> str:
    """The committed prompt, header comment stripped."""
    text = PROMPT_FILE.read_text()
    if text.lstrip().startswith("<!--"):
        text = text.split("-->", 1)[1]
    return text.strip()


def gemini_api_key() -> str:
    # base GEMINI_API_KEY is not valid for AI Studio; rotation keys _1.._7 are
    # (see study_b/spot_check.py). Take the first that exists.
    key = next((os.environ[v] for v in
                [f"GEMINI_API_KEY_{i}" for i in range(1, 8)]
                + ["GEMINI_API_KEY"] if os.environ.get(v)), None)
    if not key:
        raise SystemExit("no GEMINI_API_KEY_* set in the environment")
    return key


class Rewriter:
    """One instance per run; clients built lazily per provider."""

    def __init__(self, max_usd: float):
        self.max_usd = max_usd
        self.spent = 0.0
        self.lock = Lock()
        self.template = load_prompt_template()
        self._clients: dict[str, object] = {}

    # -- client construction (mirrors the repo's existing plumbing) --------

    def _client(self, key: str):
        if key in self._clients:
            return self._clients[key]
        if key == "gpt":
            from openai import OpenAI
            c = OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=600.0)
        elif key == "claude":
            from anthropic import Anthropic
            c = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"],
                          timeout=600.0)
        elif key == "gemini":
            from google import genai
            c = genai.Client(api_key=gemini_api_key())
        else:  # deepseek, kimi -> gateway, OpenAI-compatible
            from openai import OpenAI
            gk = os.environ.get("AI_GATEWAY_API_KEY")
            if not gk:
                raise SystemExit("AI_GATEWAY_API_KEY missing from environment")
            c = OpenAI(api_key=gk, base_url=GATEWAY, timeout=600.0)
        self._clients[key] = c
        return c

    # -- one provider call: returns (text, in_tok, out_tok, reasoning_tok) --

    def _call(self, key: str, prompt: str):
        client = self._client(key)
        if key == "gpt":
            r = client.chat.completions.create(
                model=NATIVE_ID["gpt"],
                messages=[{"role": "system", "content": SYSTEM_PROMPT},
                          {"role": "user", "content": prompt}],
                max_completion_tokens=MAX_OUT_TOKENS)
            u = r.usage
            rt = getattr(u, "completion_tokens_details", None)
            reasoning = getattr(rt, "reasoning_tokens", 0) if rt else 0
            return (r.choices[0].message.content or "",
                    u.prompt_tokens, u.completion_tokens, reasoning)
        if key == "claude":
            r = client.messages.create(
                model=NATIVE_ID["claude"], max_tokens=MAX_OUT_TOKENS,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}])
            text = "".join(b.text for b in r.content
                           if getattr(b, "type", "") == "text")
            return text, r.usage.input_tokens, r.usage.output_tokens, 0
        if key == "gemini":
            from google.genai import types
            r = client.models.generate_content(
                model=NATIVE_ID["gemini"], contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT))
            um = r.usage_metadata
            reasoning = getattr(um, "thoughts_token_count", 0) or 0
            out_tok = (um.candidates_token_count or 0) + reasoning
            return r.text or "", um.prompt_token_count or 0, out_tok, reasoning
        # gateway (deepseek, kimi)
        r = client.chat.completions.create(
            model=MODELS[key][0],
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": prompt}],
            max_tokens=MAX_OUT_TOKENS)
        u = r.usage
        rt = getattr(u, "completion_tokens_details", None)
        reasoning = getattr(rt, "reasoning_tokens", 0) if rt else 0
        return (r.choices[0].message.content or "",
                u.prompt_tokens, u.completion_tokens, reasoning)

    # -- retry loop, mirrors generate_mirrors.Runner.generate ---------------

    def rewrite(self, key: str, doc: dict) -> dict | None:
        model_id = NATIVE_ID.get(key, MODELS[key][0])
        _, pin, pout = MODELS[key]
        prompt = self.template.replace("{POST}", doc["text"])
        orig_words = len(doc["text"].split())
        retries = 0
        for attempt in range(4):
            with self.lock:
                if self.spent >= self.max_usd:
                    return {"_capped": True}
            t0 = time.time()
            try:
                text, in_tok, out_tok, reasoning = self._call(key, prompt)
                dt = time.time() - t0
                if len(text.split()) < 100:      # degenerate output
                    raise ValueError(f"short output ({len(text.split())} words)")
                frac = copy_fraction(doc["text"], text)
                if frac > COPY_THRESHOLD:        # no real edit happened
                    raise ValueError(f"trivial copy ({frac:.2f} "
                                     f"{COPY_NGRAM}-gram overlap)")
                if text.rstrip()[-1] not in TERMINAL_CHARS:  # cut off mid-sentence
                    raise ValueError("truncated output (no terminal punctuation)")
                ratio = len(text.split()) / max(orig_words, 1)
                if not (RATIO_LO <= ratio <= RATIO_HI):  # summary / expansion
                    raise ValueError(f"length drift ({ratio:.2f})")
                cost = (in_tok / 1e6) * pin + (out_tok / 1e6) * pout
                with self.lock:
                    self.spent += cost
                return {
                    "doc_id": doc["doc_id"], "source": key,
                    "model_id": model_id,
                    "original_len": orig_words,
                    "rewritten_text": text,
                    "rewritten_len": len(text.split()),
                    "model": key,
                    "in_tokens": in_tok, "out_tokens": out_tok,
                    "reasoning_tokens": reasoning, "usd": round(cost, 5),
                    "latency_s": round(dt, 2), "retries": retries,
                }
            except Exception as e:
                retries += 1
                if attempt == 3:
                    print(f"  FAIL {key} {doc['doc_id']}: {str(e)[:90]}",
                          file=sys.stderr)
                    return None
                time.sleep(5 * (attempt + 1))
        return None


def load_test_mirrors(key: str, test_ids: set[str]) -> list[dict]:
    path = MIRRORS / f"story_{key}.jsonl"
    docs = [json.loads(l) for l in open(path) if l.strip()]
    docs = [d for d in docs if d["doc_id"] in test_ids]
    docs.sort(key=lambda d: d["doc_id"])   # deterministic pilot subsets
    return docs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="",
                    help="comma list of source keys; default all five")
    ap.add_argument("--pilot", type=int, default=0,
                    help="rewrite only the first N test docs per model")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--max-usd", type=float, default=100.0)
    args = ap.parse_args()

    keys = [k.strip() for k in args.model.split(",") if k.strip()] or list(MODELS)
    for k in keys:
        if k not in MODELS:
            raise SystemExit(f"unknown model key {k}; have {list(MODELS)}")

    splits = json.load(open(SPLITS))
    test_ids = {d for d, s in splits["doc_split"].items() if s == "test"}
    print(f"test split: {len(test_ids)} prompts", file=sys.stderr)

    OUT.mkdir(parents=True, exist_ok=True)
    rewriter = Rewriter(args.max_usd)
    grand_total = 0
    for key in keys:
        docs = load_test_mirrors(key, test_ids)
        if args.pilot:
            docs = docs[:args.pilot]
        path = OUT / f"rewritten_{key}.jsonl"
        done = set()
        if path.exists():
            done = {json.loads(l)["doc_id"] for l in open(path) if l.strip()}
        todo = [d for d in docs if d["doc_id"] not in done]
        print(f"\n=== {key} ({NATIVE_ID.get(key, MODELS[key][0])}): "
              f"{len(todo)} to rewrite ({len(done)} done) ===", file=sys.stderr)
        if not todo:
            continue
        f = open(path, "a")
        n_ok = n_fail = 0
        capped = False
        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            futs = {ex.submit(rewriter.rewrite, key, d): d["doc_id"]
                    for d in todo}
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
                              f"spent=${rewriter.spent:.2f}", file=sys.stderr)
                else:
                    n_fail += 1
        f.close()
        grand_total += n_ok
        print(f"  {key}: {n_ok} ok, {n_fail} failed, "
              f"running spend ${rewriter.spent:.2f}", file=sys.stderr)
        if capped:
            print(f"STOPPED: spend cap ${args.max_usd} reached", file=sys.stderr)
            return 2

    print(f"\ntotal rewritten this run: {grand_total}; "
          f"spend ${rewriter.spent:.2f}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
