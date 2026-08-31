"""Symmetric text normalization for all seven sources (pre-M6).

Design rule: ONE normalizer, applied identically to every source. Each rule is
a no-op where the artifact does not occur, so the *processing* is symmetric
even though the *effect* is not - which is exactly right, because the
artifacts themselves are asymmetric (see artifacts/REPLICATION_CONTRACT.md).

Artifacts removed, measured 2026-07-25 on the real corpora:

| artifact              | human | AI    | why it must go                       |
|-----------------------|-------|-------|--------------------------------------|
| markdown syntax       | ~0    | 6.1 headings, 50.8 bold/doc | AI writes markdown natively; human text lost its formatting in HTML extraction. Keeping it would let the pipeline "detect" our data pipeline. |
| byline / date lines   | 105   | 0     | page furniture, not article prose    |
| share/subscribe CTA   | 89    | 0     | ditto                                |
| table of contents     | 30    | 0     | ditto                                |
| "N min read"          | 17    | 0     | ditto                                |

Stripping to plain prose also moves us CLOSER to the paper, whose corpus was
plain prose on both sides (Books3 stories vs generated fiction).

Conservative by construction: furniture rules only fire on short standalone
lines, never mid-paragraph, so article sentences cannot be eaten.

Usage:
  .venv/bin/python -m study_b.normalize --selftest
  .venv/bin/python -m study_b.normalize build   # writes the unified corpus
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CORPUS = Path("outputs/study_b/corpus/story_human_frozen.parquet")
MIRRORS = Path("outputs/study_b/mirrors")
OUT = Path("outputs/study_b/corpus/unified_corpus.parquet")

# --- markdown ---------------------------------------------------------------
_MD_RULES = [
    (re.compile(r"^\s{0,3}#{1,6}\s+", re.M), ""),          # headings
    (re.compile(r"\*\*([^*\n]+)\*\*"), r"\1"),               # bold
    (re.compile(r"__([^_\n]+)__"), r"\1"),
    (re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)"), r"\1"),      # italics
    (re.compile(r"^\s{0,4}[-*+]\s+", re.M), ""),            # bullet markers
    (re.compile(r"^\s{0,4}\d+[.)]\s+", re.M), ""),          # numbered markers
    (re.compile(r"^\s{0,3}>\s?", re.M), ""),                # blockquote
    (re.compile(r"`([^`\n]*)`"), r"\1"),                     # inline code
    (re.compile(r"!\[[^\]]*\]\([^)]*\)"), ""),               # images
    (re.compile(r"\[([^\]]+)\]\([^)]*\)"), r"\1"),           # links -> anchor
    (re.compile(r"^\s*([-*_])\s*(\1\s*){2,}$", re.M), ""),   # horizontal rules
]

# --- page furniture (standalone short lines only) ---------------------------
_FURNITURE = re.compile(
    r"^\s*(?:"
    r"table of contents"
    r"|(?:share|subscribe|sign up|follow us|related (?:posts?|articles?)|read more)\b.{0,40}"
    r"|by\s+[A-Z][\w.'-]+(?:\s+[A-Z][\w.'-]+){0,3}"
    r"|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}"
    r"|(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*,?\s+.{0,24}\d{4}"
    r"|\d{1,2}\s*min(?:ute)?s?\s+read"
    r"|\d+\s*(?:comments?|shares?|likes?)"
    r")\s*$",
    re.IGNORECASE)

MAX_FURNITURE_WORDS = 9   # never touch a line long enough to be real prose


def strip_markdown(text: str) -> str:
    for pat, rep in _MD_RULES:
        text = pat.sub(rep, text)
    return text


def strip_furniture(text: str) -> str:
    out = []
    for line in text.split("\n"):
        if len(line.split()) <= MAX_FURNITURE_WORDS and _FURNITURE.match(line):
            continue
        out.append(line)
    return "\n".join(out)


def normalize(text: str) -> str:
    """The single normalizer applied to every source."""
    text = strip_markdown(text)
    text = strip_furniture(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
def selftest() -> int:
    cases = [
        # (input, must_contain, must_not_contain)
        ("## Heading\n\n**Bold** and *italic* text.",
         ["Heading", "Bold and italic text."], ["##", "**"]),
        ("- first item\n- second item", ["first item", "second item"], ["- "]),
        ("Table of contents\nReal sentence follows here.",
         ["Real sentence follows here."], ["Table of contents"]),
        ("By Tom Okman\nNovember 11, 2022\nThe article begins.",
         ["The article begins."], ["Tom Okman", "November 11, 2022"]),
        ("5 min read\nContent starts.", ["Content starts."], ["min read"]),
        # must NOT eat real prose that merely starts with a trigger word
        ("Share this insight with your team because it changes how you plan "
         "quarterly budgets and staffing.",
         ["Share this insight with your team"], []),
        ("By the time the migration finished, latency had dropped by half and "
         "the team could finally sleep.",
         ["By the time the migration finished"], []),
        ("[Read the docs](https://x.io/docs) for details.",
         ["Read the docs for details."], ["https://x.io"]),
    ]
    fails = 0
    for i, (src, must, must_not) in enumerate(cases, 1):
        got = normalize(src)
        for m in must:
            if m not in got:
                print(f"  FAIL {i}: missing {m!r} in {got!r}"); fails += 1
        for m in must_not:
            if m in got:
                print(f"  FAIL {i}: still contains {m!r} in {got!r}"); fails += 1
    print(f"selftest: {len(cases)} cases, {fails} failures")
    return 1 if fails else 0


def build() -> int:
    import pandas as pd

    hum = pd.read_parquet(CORPUS)
    rows = [{"doc_id": r.doc_id, "source": "human", "domain": r.domain,
             "stratum": r.stratum, "vertical": r.vertical, "title": r.title,
             "text": normalize(r.story_human)} for r in hum.itertuples()]
    for p in sorted(MIRRORS.glob("story_*.jsonl")):
        src = p.stem.replace("story_", "")
        for line in open(p):
            r = json.loads(line)
            rows.append({"doc_id": r["doc_id"], "source": src,
                         "domain": r["domain"], "stratum": r["stratum"],
                         "vertical": r["vertical"],
                         "title": r["text"].strip().split("\n")[0][:200],
                         "text": normalize(r["text"])})
    df = pd.DataFrame(rows)
    df["words"] = df.text.str.split().str.len()
    df.to_parquet(OUT, index=False)
    print(f"unified corpus: {len(df)} docs, {df.source.nunique()} sources -> {OUT}")
    print(df.groupby("source").agg(n=("doc_id", "count"),
                                   mean_words=("words", "mean")).round(0).to_string())
    md = df.text.str.contains(r"^#{1,6} |\*\*", regex=True).groupby(df.source).sum()
    print("\nresidual markdown markers per source:")
    print(md.to_string())
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", nargs="?", default="selftest",
                    choices=["selftest", "build"])
    a = ap.parse_args()
    return selftest() if a.cmd == "selftest" else build()


if __name__ == "__main__":
    sys.exit(main())
