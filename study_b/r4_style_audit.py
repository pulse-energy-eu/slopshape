#!/usr/bin/env python
"""R4: style-dependence audit of the v2 taxonomy.

Same procedure as v1's style_audit.py - gpt-5.4, 3 independent runs, verbatim
paper definitions, strict exclusion rule - retargeted at the v2 deduped
taxonomy and its B2B dimension names. Two adaptations, both declared:
  - the style dimension key is "writing_style" (v2 schema), not "style";
  - the prompt's gray-zone rule is stated in B2B terms (the fiction wording
    named events/characters/closure, which do not exist here); the KEPT
    definition of style itself is verbatim from the paper.

STRICT EXCLUSION RULE (pre-registered, unchanged): a feature is excluded from
the Narrative-strict variant iff it belongs to the style dimension OR its
majority rating across the 3 runs is "high".

Runs through the AI gateway (v1 used OpenAI direct; same model).

  .venv/bin/python -m study_b.r4_style_audit [--taxonomy PATH] [--runs 3]
"""
import argparse
import concurrent.futures as cf
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from study_b.generate_mirrors import GATEWAY  # noqa: E402

MODEL = "openai/gpt-5.4"          # the paper's audit model, unchanged
STYLE_DIM = "writing_style"       # v2 schema key for the mandated style bucket
OUT = Path("outputs/study_b/r4")

PROMPT = """You are auditing one feature of a content-analysis taxonomy for \
style dependence.

Definition (verbatim from the study being replicated):
"Style features concern sentence- and phrase-level texture (diction, syntax, \
rhythm, figurative density, tonal register, and prose-level allusion), whereas \
non-style features concern narrative content and structure."

In this study the texts are B2B blog posts, so "content and structure" means \
the post's purpose, audience framing, argument structure, explanation, \
evidence and sourcing, voices, actionable guidance, commercial integration, \
time anchoring, and page format. The gray-zone rule is unchanged: if a feature \
can only be answered from prose texture, it is style; if it is primarily about \
content or structure and prose choices are incidental, it is non-style.

Rate this feature's style dependence as "high", "medium", or "low":
- high   = can only be answered from prose texture
- medium = partially answerable from content, but prose texture materially informs it
- low    = primarily about content or structure; prose choices are incidental

FEATURE
  id: {fid}
  dimension: {dim}
  name: {name}
  question: {question}
  answer options: {vals}

Return ONLY JSON: {{"rating": "high|medium|low", "rationale": "<one sentence>"}}"""


def features_of(tax_path: Path) -> list[tuple]:
    raw = json.load(open(tax_path))
    raw = raw.get("feature_taxonomy", raw)
    out = []
    for dim, dbody in raw.items():
        if not isinstance(dbody, dict):
            continue
        for asp, abody in (dbody.get("aspects") or {}).items():
            feats = abody.get("features") or []
            for f in feats:
                if isinstance(f, dict) and f.get("id"):
                    out.append((f["id"], dim, f.get("name", ""),
                                f.get("question", ""),
                                f.get("values") or f.get("options") or []))
    return out


def audit_one(client, rec, run) -> dict:
    fid, dim, name, question, vals = rec
    p = PROMPT.format(fid=fid, dim=dim, name=name, question=question[:400],
                      vals=", ".join(map(str, vals))[:500])
    for attempt in range(4):
        try:
            r = client.chat.completions.create(
                model=MODEL, messages=[{"role": "user", "content": p}],
                max_tokens=800)
            import re
            txt = r.choices[0].message.content or ""
            m = re.search(r"\{.*\}", txt, re.S)
            d = json.loads(m.group(0) if m else txt)
            rating = str(d.get("rating", "")).lower()
            if rating in ("high", "medium", "low"):
                return {"run": run, "fid": fid, "dim": dim, "rating": rating,
                        "rationale": str(d.get("rationale", ""))[:300]}
            raise ValueError(f"bad rating {rating!r}")
        except Exception as e:
            if attempt == 3:
                return {"run": run, "fid": fid, "dim": dim, "rating": "ERROR",
                        "rationale": str(e)[:120]}
            time.sleep(3 * (attempt + 1))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--taxonomy",
                    default="outputs/study_b/r3/dedup/condensed_taxonomy_0.85.json")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--concurrency", type=int, default=10)
    args = ap.parse_args()

    tax_path = Path(args.taxonomy)
    if not tax_path.exists():
        cands = sorted(Path("outputs/study_b/r3/dedup").glob("*taxonomy*.json"))
        if not cands:
            raise SystemExit(f"no taxonomy at {tax_path} and none in r3/dedup")
        tax_path = cands[0]
        print(f"using {tax_path}", file=sys.stderr)

    from openai import OpenAI
    client = OpenAI(api_key=os.environ["AI_GATEWAY_API_KEY"],
                    base_url=GATEWAY, timeout=300.0)
    OUT.mkdir(parents=True, exist_ok=True)

    feats = features_of(tax_path)
    print(f"style audit: {len(feats)} features x {args.runs} runs", file=sys.stderr)
    raw_path = OUT / "ratings_v2.jsonl"
    done = set()
    if raw_path.exists():
        done = {(r["run"], r["fid"]) for r in map(json.loads, open(raw_path))
                if r["rating"] != "ERROR"}
    todo = [(rec, run) for run in range(1, args.runs + 1) for rec in feats
            if (run, rec[0]) not in done]
    print(f"todo {len(todo)} (resume: {len(done)} done)", file=sys.stderr)

    with open(raw_path, "a") as fh, cf.ThreadPoolExecutor(args.concurrency) as ex:
        futs = [ex.submit(audit_one, client, rec, run) for rec, run in todo]
        for i, fu in enumerate(cf.as_completed(futs), 1):
            fh.write(json.dumps(fu.result()) + "\n")
            fh.flush()
            if i % 200 == 0:
                print(f"  {i}/{len(todo)}", file=sys.stderr)

    rows = [json.loads(l) for l in open(raw_path) if l.strip()]
    by = {}
    for r in rows:
        if r["rating"] != "ERROR":
            by.setdefault(r["fid"], []).append(r["rating"])
    exact = sum(1 for v in by.values() if len(set(v)) == 1) / max(1, len(by))
    maj = {f: Counter(v).most_common(1)[0][0] for f, v in by.items()}
    dim_of = {rec[0]: rec[1] for rec in feats}
    excl = sorted(f for f in maj if dim_of.get(f) == STYLE_DIM or maj[f] == "high")
    summary = {
        "taxonomy": str(tax_path), "model": MODEL, "runs": args.runs,
        "features": len(feats), "rated": len(by),
        "exact_3run_agreement": round(exact, 3),
        "rating_distribution": dict(Counter(maj.values())),
        "excluded_from_narrative_strict": len(excl),
        "excluded_by_dimension": dict(Counter(dim_of[f] for f in excl)),
        "narrative_strict_features": len(by) - len(excl),
    }
    (OUT / "style_audit_summary.json").write_text(json.dumps(summary, indent=2))
    (OUT / "excluded_features.json").write_text(json.dumps(excl, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
