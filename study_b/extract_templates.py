#!/usr/bin/env python
"""Stage 2 (R2): template extraction against the FROZEN B2B schema.

Fills artifacts/TEMPLATE_SCHEMA_V2.md (PI-frozen 2026-08-11) for every text:
human docs (story_human_frozen.parquet) + all mirror stories (mirrors/story_*.jsonl).
The schema JSON block inside the frozen file is the single source of truth.

Pilot gate: before full spend, run --pilot N (default 50
human docs, seeded) on BOTH gpt-5.6-luna and gpt-5.6-terra; luna is adopted
iff field completeness >= 0.95 and GLOBAL-field agreement with terra >= 0.80.
Otherwise the full run uses terra (cost delta logged).

Full run: resume-safe JSONL keyed (doc_id, source); one row per text.
Gateway quirk: no response_format for these models - regex JSON extraction.

  .venv/bin/python -m study_b.extract_templates --pilot 50        # gate report
  .venv/bin/python -m study_b.extract_templates --model luna      # full run
"""
import argparse
import concurrent.futures as cf
import json
import random
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from study_b.generate_mirrors import GATEWAY, gateway_balance  # noqa: E402

SCHEMA_FILE = Path("artifacts/TEMPLATE_SCHEMA_V2.md")
OUT = Path("outputs/study_b/templates")
SEED = 202608
MODELS = {  # key -> (gateway id, $/M in, $/M out)
    "luna": ("openai/gpt-5.6-luna", 0.2, 1.2),
    "terra": ("openai/gpt-5.6-terra", 2.0, 12.0),
}
PILOT_COMPLETENESS_GATE = 0.95
PILOT_AGREEMENT_GATE = 0.80
# Gate refinement (PI 2026-08-11, after round-1 pilot): agreement is gated on
# SINGLE-SELECT fields only. Free-text GLOBAL fields cannot exact-match by
# construction (terra-vs-terra self-agreement over ALL GLOBAL fields = 0.64,
# over single-select = 0.884 - the measurable ceiling). Round-1 files kept as
# pilot_*_r1.jsonl.
SINGLE_SELECT = {
    ("purpose_reader_payoff", "main_purpose"),
    ("purpose_reader_payoff", "content_format"),
    ("structure_and_flow", "overall_flow"),
    ("structure_and_flow", "building_block"),
    ("structure_and_flow", "ordering_principle"),
    ("explanation_depth", "knowledge_type"),
    ("explanation_depth", "assumed_knowledge"),
    ("evidence_and_proof", "use_of_numbers"),
    ("voices_and_sources", "main_voice"),
    ("voices_and_sources", "format_of_voices"),
    ("voices_and_sources", "how_reader_is_addressed"),
    ("actionability", "how_actionable"),
    ("actionability", "action_structure"),
    ("actionability", "who_acts"),
    ("brand_product_integration", "product_role"),
    ("brand_product_integration", "where_product_appears"),
    ("brand_product_integration", "sales_pressure"),
    ("brand_product_integration", "ending_and_next_step"),
    ("timeliness", "time_sensitivity"),
    ("timeliness", "change_story"),
    ("page_format_navigation", "page_type"),
    ("page_format_navigation", "self_containment"),
    ("writing_style", "formality"),
}


def _options(desc: str) -> list[str]:
    tail = desc.split(":", 1)[1] if ":" in desc else desc
    opts = []
    for o in tail.split(","):
        o = o.strip(" .").removeprefix("or ").strip()
        if o:
            opts.append(o)
    return opts

PROMPT = """You are filling a fixed structural schema for ONE blog post. The schema \
decomposes B2B blog posts into structural dimensions; each dimension has fields \
with scope GLOBAL (one value for the whole post) or LOCAL (a list of instances, \
each tagged with the section it occurs in).

Rules:
- Fill EVERY field. If a field is genuinely absent from the post, use the string \
"absent" (GLOBAL) or an empty list (LOCAL). Never omit a key.
- Fields marked CHOOSE EXACTLY ONE: answer with exactly one of the listed values, \
verbatim, nothing else.
- Other GLOBAL fields: a short value; when the description names categories, use \
those category terms verbatim (a short comma-separated list if several apply).
- LOCAL fields: a list of {{"section": "<heading or first words>", "value": "<short \
extraction>"}} objects.
- Judge only what is in the text. No commentary outside the JSON.

THE SCHEMA (dimension -> fields):
{schema}

THE POST:
TITLE: {title}
{text}

Return ONLY a JSON object with exactly the dimension keys, each mapping to an \
object with exactly that dimension's field names as keys."""


def load_schema() -> dict:
    m = re.search(r"```json\n(.*?)\n```", SCHEMA_FILE.read_text(), re.S)
    if not m:
        raise SystemExit(f"no JSON block in {SCHEMA_FILE}")
    return json.loads(m.group(1))


def schema_prompt_block(schema: dict) -> str:
    lines = []
    for dim, spec in schema.items():
        lines.append(f"{dim}: {spec['definition']}")
        for f in spec["fields"]:
            desc = f["description"]
            if (dim, f["name"]) in SINGLE_SELECT:
                opts = " | ".join(_options(desc))
                desc = f"{desc} CHOOSE EXACTLY ONE: {opts}"
            lines.append(f"  - {f['name']} [{f['scope']}]: {desc}")
    return "\n".join(lines)


def iter_texts(human_only: bool = False):
    """Yield dicts: doc_id, source, domain, vertical, title, text."""
    import pandas as pd
    h = pd.read_parquet("outputs/study_b/corpus/story_human_frozen.parquet")
    for r in h.itertuples():
        yield {"doc_id": r.doc_id, "source": "human", "domain": r.domain,
               "vertical": getattr(r, "vertical", ""),
               "title": getattr(r, "title", ""), "text": r.story_human}
    if human_only:
        return
    for f in sorted(Path("outputs/study_b/mirrors").glob("story_*.jsonl")):
        for line in open(f):
            r = json.loads(line)
            yield {"doc_id": r["doc_id"], "source": r["source"],
                   "domain": r.get("domain", ""), "vertical": r.get("vertical", ""),
                   "title": "", "text": r["text"]}


def completeness(rec: dict, schema: dict) -> float:
    """Share of schema fields present with a non-null value in an extraction."""
    have = total = 0
    for dim, spec in schema.items():
        d = rec.get(dim) or {}
        for f in spec["fields"]:
            total += 1
            v = d.get(f["name"])
            if v is None:
                continue
            have += 1  # "absent"/[] count: the field was consciously filled
    return have / max(1, total)


class Extractor:
    def __init__(self, model_key: str):
        from openai import OpenAI
        import os
        self.model_id, self.pin, self.pout = MODELS[model_key]
        self.client = OpenAI(api_key=os.environ["AI_GATEWAY_API_KEY"],
                             base_url=GATEWAY, timeout=600.0)
        self.spent = 0.0

    def extract(self, item: dict, schema_block: str) -> dict | None:
        words = item["text"].split()
        prompt = PROMPT.format(schema=schema_block, title=item["title"] or "(untitled)",
                               text=" ".join(words[:2600]))
        for attempt in range(3):
            try:
                r = self.client.chat.completions.create(
                    model=self.model_id,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=6000)
                u = r.usage
                self.spent += (u.prompt_tokens * self.pin
                               + u.completion_tokens * self.pout) / 1e6
                txt = r.choices[0].message.content or ""
                m = re.search(r"\{.*\}", txt, re.S)
                tpl = json.loads(m.group(0) if m else txt)
                return {"doc_id": item["doc_id"], "source": item["source"],
                        "domain": item["domain"], "vertical": item["vertical"],
                        "model_id": self.model_id, "template": tpl}
            except Exception as e:
                if attempt == 2:
                    return {"doc_id": item["doc_id"], "source": item["source"],
                            "domain": item["domain"], "vertical": item["vertical"],
                            "model_id": self.model_id, "error": str(e)[:200]}
                time.sleep(8 * (attempt + 1))


def run_pilot(n: int, schema: dict, block: str) -> int:
    docs = [d for d in iter_texts(human_only=True)]
    rng = random.Random(SEED)
    sample = rng.sample(docs, min(n, len(docs)))
    OUT.mkdir(parents=True, exist_ok=True)
    results = {}
    for key in ("luna", "terra"):
        ex = Extractor(key)
        rows = []
        with cf.ThreadPoolExecutor(8) as pool:
            for rec in pool.map(lambda it: ex.extract(it, block), sample):
                rows.append(rec)
        (OUT / f"pilot_{key}.jsonl").write_text(
            "\n".join(json.dumps(r) for r in rows) + "\n")
        ok = [r for r in rows if "template" in r]
        comp = sum(completeness(r["template"], schema) for r in ok) / max(1, len(ok))
        results[key] = {"rows": rows, "ok": len(ok), "completeness": comp,
                        "spend": ex.spent}
        print(f"pilot {key}: {len(ok)}/{len(rows)} parsed, "
              f"completeness {comp:.3f}, spend ${ex.spent:.2f}", file=sys.stderr)
    # agreement luna vs terra (same doc, exact-match after casefold, substring
    # tolerated); gated on the SINGLE_SELECT subset, all-GLOBAL reported too
    by_doc = {r["doc_id"]: r["template"] for r in results["terra"]["rows"]
              if "template" in r}
    ag_a = tot_a = ag_s = tot_s = 0
    for r in results["luna"]["rows"]:
        t2 = by_doc.get(r["doc_id"])
        if "template" not in r or not t2:
            continue
        for dim, spec in schema.items():
            for f in spec["fields"]:
                if f["scope"] != "GLOBAL":
                    continue
                a = str((r["template"].get(dim) or {}).get(f["name"], "")).casefold().strip()
                b = str((t2.get(dim) or {}).get(f["name"], "")).casefold().strip()
                if a and b:
                    hit = (a == b or a in b or b in a)
                    tot_a += 1
                    ag_a += hit
                    if (dim, f["name"]) in SINGLE_SELECT:
                        tot_s += 1
                        ag_s += hit
    ag_all, ag_single = ag_a / max(1, tot_a), ag_s / max(1, tot_s)
    luna_c = results["luna"]["completeness"]
    verdict = "luna" if (luna_c >= PILOT_COMPLETENESS_GATE
                         and ag_single >= PILOT_AGREEMENT_GATE) else "terra"
    report = {"pilot_n": len(sample), "luna_completeness": luna_c,
              "terra_completeness": results["terra"]["completeness"],
              "single_select_agreement": ag_single,
              "global_field_agreement": ag_all,
              "gates": {"completeness": PILOT_COMPLETENESS_GATE,
                        "agreement_single_select": PILOT_AGREEMENT_GATE},
              "verdict": verdict,
              "pilot_spend": {k: round(results[k]["spend"], 2) for k in results}}
    (OUT / "PILOT_REPORT.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    print(f"VERDICT: use {verdict} for the full run", file=sys.stderr)
    return 0


def run_full(model_key: str, concurrency: int, max_usd: float) -> int:
    schema = load_schema()
    block = schema_prompt_block(schema)
    OUT.mkdir(parents=True, exist_ok=True)
    outfile = OUT / "templates_v2.jsonl"
    done = set()
    if outfile.exists():
        for l in open(outfile):
            r = json.loads(l)
            if "template" in r:
                done.add((r["doc_id"], r["source"]))
    todo = [it for it in iter_texts() if (it["doc_id"], it["source"]) not in done]
    print(f"templates: {len(todo)} to extract ({len(done)} done)", file=sys.stderr)
    ex = Extractor(model_key)
    n_ok = n_err = 0
    with open(outfile, "a") as fh, cf.ThreadPoolExecutor(concurrency) as pool:
        for i, rec in enumerate(pool.map(lambda it: ex.extract(it, block), todo), 1):
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            n_ok += "template" in rec
            n_err += "error" in rec
            if i % 100 == 0:
                print(f"  [{i}/{len(todo)}] ok={n_ok} err={n_err} "
                      f"spent=${ex.spent:.2f}", file=sys.stderr)
            if ex.spent > max_usd:
                print(f"STOPPED: spend cap ${max_usd} reached", file=sys.stderr)
                return 1
    print(f"done: {n_ok} ok, {n_err} failed (rerun to retry), "
          f"spend ${ex.spent:.2f}", file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", type=int, default=0, help="run N-doc pilot gate")
    ap.add_argument("--model", choices=list(MODELS), default=None)
    ap.add_argument("--concurrency", type=int, default=12)
    ap.add_argument("--max-usd", type=float, default=250.0)
    args = ap.parse_args()
    schema = load_schema()
    block = schema_prompt_block(schema)
    if args.pilot:
        return run_pilot(args.pilot, schema, block)
    if not args.model:
        rep = OUT / "PILOT_REPORT.json"
        if not rep.exists():
            raise SystemExit("no --model and no PILOT_REPORT.json - run --pilot first")
        args.model = json.loads(rep.read_text())["verdict"]
        print(f"model from pilot verdict: {args.model}", file=sys.stderr)
    return run_full(args.model, args.concurrency, args.max_usd)


if __name__ == "__main__":
    sys.exit(main())
