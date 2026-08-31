#!/usr/bin/env python
"""Funnel step 2: company-fit screen (LLM, authorship-blind).

Judges each domain's COMPANY (never any writing) from frame metadata plus a
live homepage <title>/meta-description fetch. Inclusive rule: keep anything
where organic search is a PLAUSIBLE acquisition channel; drop only clear
anti-personas (agency/consultancy, media/publisher, government/nonprofit/edu,
dead or unidentifiable). Model: gpt-5.6-luna via AI Gateway, 2 votes;
disagreement -> keep. Output vertical label normalized to the 7 strata.

Resume-safe: outputs/study_b/frames/icp_screen.jsonl, one row per domain.
This prompt is published in the paper's appendix.

  .venv/bin/python -m study_b.icp_screen [--limit N] [--concurrency 12]
"""
import argparse
import concurrent.futures as cf
import csv
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

FRAME = Path("outputs/study_b/frames/composite_frame.csv")
OUT = Path("outputs/study_b/frames/icp_screen.jsonl")
GATEWAY = "https://ai-gateway.vercel.sh/v1"
MODEL = "openai/gpt-5.6-luna"
VERTICALS = ["software_saas", "fintech_insurance", "health", "ecommerce_retail",
             "devtools", "edtech", "services_other"]
UA = {"User-Agent": "Mozilla/5.0 (research; sitefire slop-benchmark)"}

PROMPT = """You are screening companies for a research corpus of B2B/B2C \
content-marketing blogs. Judge the COMPANY only - never any writing style.

KEEP if the company sells a product or service for which organic search is a \
plausible customer-acquisition channel (software, SaaS, fintech, insurance, \
health services/products, e-commerce, developer tools, education products, \
tech-enabled services - B2B and B2C both qualify).

DROP only clear anti-personas:
- marketing/advertising/PR/SEO agencies and consultancies (they write ABOUT \
marketing; their blogs are not ordinary company content marketing)
- media companies and publishers (content IS their product)
- government, nonprofit, or educational institutions
- domains that appear dead, parked, or unidentifiable as a company

COMPANY
  domain: {domain}
  name: {company}
  listed category: {industry_raw}
  homepage title/description: {homepage}

Return ONLY JSON:
{{"keep": true/false, "vertical": "<one of {verticals}>", "reason": "<one short sentence>"}}"""


def fetch_homepage(domain: str) -> str:
    for scheme in ("https", "http"):
        try:
            r = requests.get(f"{scheme}://{domain}", headers=UA, timeout=6,
                             allow_redirects=True)
            html = r.text[:20000]
            title = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
            desc = re.search(
                r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']{0,300})',
                html, re.I)
            parts = [t.group(1).strip()[:150] for t in (title,) if t]
            if desc:
                parts.append(desc.group(1).strip()[:200])
            return " | ".join(" ".join(p.split()) for p in parts) or "(no title found)"
        except requests.RequestException:
            continue
    return "(unreachable)"


def screen_one(client, row: dict) -> dict:
    homepage = fetch_homepage(row["domain"])
    prompt = PROMPT.format(domain=row["domain"], company=row.get("company", ""),
                           industry_raw=row.get("industry_raw", ""),
                           homepage=homepage, verticals=", ".join(VERTICALS))
    votes = []
    for _ in range(2):
        for attempt in range(3):
            try:
                # gateway rejects response_format for this model (v1 lesson);
                # luna returns clean JSON from the prompt alone
                r = client.chat.completions.create(
                    model=MODEL, messages=[{"role": "user", "content": prompt}],
                    max_tokens=160)
                txt = r.choices[0].message.content or ""
                m = re.search(r"\{.*\}", txt, re.S)
                d = json.loads(m.group(0) if m else txt)
                v = str(d.get("vertical", "")).strip()
                votes.append({"keep": bool(d.get("keep")),
                              "vertical": v if v in VERTICALS else "services_other",
                              "reason": str(d.get("reason", ""))[:160]})
                break
            except Exception:
                if attempt == 2:
                    votes.append({"keep": True, "vertical": "services_other",
                                  "reason": "SCREEN_ERROR - kept inclusive"})
                time.sleep(2 * (attempt + 1))
    keep = votes[0]["keep"] if votes[0]["keep"] == votes[1]["keep"] else True
    vertical = votes[0]["vertical"] if keep else votes[0]["vertical"]
    return {"domain": row["domain"], "keep": keep, "vertical": vertical,
            "frame_vertical": row.get("vertical", ""), "source": row.get("source", ""),
            "homepage": homepage[:200], "votes": votes,
            "agree": votes[0]["keep"] == votes[1]["keep"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--concurrency", type=int, default=12)
    args = ap.parse_args()

    from openai import OpenAI
    key = os.environ.get("AI_GATEWAY_API_KEY")
    if not key:
        raise SystemExit("AI_GATEWAY_API_KEY missing; source .env")
    client = OpenAI(api_key=key, base_url=GATEWAY, timeout=120.0)

    rows = list(csv.DictReader(open(FRAME)))
    done = set()
    if OUT.exists():
        done = {json.loads(l)["domain"] for l in open(OUT) if l.strip()}
    todo = [r for r in rows if r["domain"] not in done]
    if args.limit:
        todo = todo[:args.limit]
    print(f"ICP screen: {len(todo)} to screen ({len(done)} done)", file=sys.stderr)

    n_keep = n_drop = 0
    with open(OUT, "a") as fh, cf.ThreadPoolExecutor(args.concurrency) as ex:
        futs = [ex.submit(screen_one, client, r) for r in todo]
        for i, fu in enumerate(cf.as_completed(futs), 1):
            rec = fu.result()
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            n_keep += rec["keep"]; n_drop += not rec["keep"]
            if i % 250 == 0:
                print(f"  {i}/{len(todo)} (keep {n_keep} / drop {n_drop})",
                      file=sys.stderr)
    print(f"screened {len(todo)}: keep {n_keep}, drop {n_drop}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
