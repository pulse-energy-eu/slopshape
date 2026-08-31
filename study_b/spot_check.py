"""Stage 2 spot-check: verify per-domain yield of usable informational posts.

For each qualified domain: fetch a seeded sample of 3-5 archived
posts (pre-ChatGPT snapshots only), extract prose, then apply the three
filters that qualification could not test:
  - language (the study is English-only; EU domains often blog locally)
  - length (>=500 words of extracted prose)
  - genre (keep only informational content marketing - the genre
    AI-SEO tools produce - via title/URL heuristic + flash-LLM classifier)

Outputs (resume-safe, append per domain):
  outputs/study_b/spotcheck/posts.csv          per-post detail
  outputs/study_b/spotcheck/decision_list.csv  per-domain aggregate for the
                                               approval gate

Usage:
  .venv/bin/python -m study_b.spot_check [--limit N] [--per-domain 5]
      [--model gemini-3-flash] [--pace 4.0]
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import sys
import time
from pathlib import Path

import requests
import trafilatura

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

OUT = Path("outputs/study_b/spotcheck")
UA = {"User-Agent": "sitefire-slop-benchmark/0.1 (research; jochen@sitefire.ai)"}
CDX = "http://web.archive.org/cdx/search/cdx"
CUTOFF = "20221129"  # last allowed snapshot day (pre-ChatGPT)

WORD_RE = re.compile(r"\b\w\w+\b")

# quick stopword voting for the languages our EU strata may blog in
LANG_MARKERS = {
    "en": set("the and for with that this from are was were have has not you your".split()),
    "de": set("der die das und für mit nicht ist ein eine auch bei werden oder".split()),
    "fr": set("le la les des une est pour dans avec sur pas vous nous par".split()),
    "it": set("il di che per con una sono del alla più anche come nel".split()),
    "es": set("el los las una para con por del est como más pero sus".split()),
}

# stage-1 genre heuristic
POS_TITLE = re.compile(
    r"how to|guide|what is|what are|why |best |top \d|\d+ (ways|tips|steps|"
    r"examples|reasons|things)|vs\.?\s|versus|checklist|template|tutorial|"
    r"complete|ultimate|beginner|explained|definition", re.IGNORECASE)
NEG_TITLE = re.compile(
    r"announc|raises|funding|series [a-e]\b|welcome|joins|hiring|we're|"
    r"press release|earnings|quarter|q[1-4] 20|award|winner|partnership|"
    r"event|webinar|conference|meetup|changelog|release notes|version \d|"
    r"now available|introducing|launch", re.IGNORECASE)

NON_ARTICLE_URL = re.compile(
    r"/(tag|category|author|page|feed|amp|search|wp-)|[?#]|\.(xml|jpg|png|pdf)$",
    re.IGNORECASE)

GENRE_PROMPT = """You are classifying the genre of a blog post. You see only \
the title and the first ~300 words. Classify into exactly one of:
- informational: how-to, guide, listicle, comparison, definition/explainer, \
educational content written to inform a general professional audience
- news_pr: company news, press-release style, funding, partnerships, awards
- product_announcement: feature launches, release notes, product updates
- case_study: customer story or results write-up
- culture_hiring: team, careers, values, events
- opinion_essay: personal essay, hot take, editorial
- other: anything else

Respond with ONLY a JSON object: {"genre": "<label>"}

TITLE: {title}

TEXT:
{text}
"""


def detect_lang(text: str) -> str:
    # script guard: mostly non-Latin text is never English, regardless of
    # stopword votes (caught 11 Greek posts that slipped into M2's corpus)
    head = text[:4000]
    letters = [ch for ch in head if ch.isalpha()]
    if letters and sum(1 for ch in letters if ord(ch) > 0x24F) / len(letters) > 0.3:
        return "other"
    toks = [t.lower() for t in WORD_RE.findall(text[:8000])]
    if not toks:
        return "other"
    votes = {lang: sum(t in words for t in toks)
             for lang, words in LANG_MARKERS.items()}
    lang, n = max(votes.items(), key=lambda kv: kv[1])
    return lang if n > 0 else "other"


def cdx_article_urls(domain: str, best_path: str, pace: float) -> list[tuple[str, str]]:
    """Return [(timestamp, original_url)] of candidate article snapshots."""
    if best_path.endswith("."):
        pattern = f"{best_path}{domain}/*"
    else:
        pattern = f"{domain}/{best_path or 'blog/'}*"
    # no lower time bound: qualification counted all pre-cutoff snapshots,
    # and older posts are equally valid pre-AI human content (year is
    # recorded per post for later filtering)
    params = {"url": pattern, "to": CUTOFF,
              "filter": ["statuscode:200", "mimetype:text/html"],
              "collapse": "urlkey", "limit": "500", "output": "json"}
    try:
        r = requests.get(CDX, params=params, headers=UA, timeout=60)
        time.sleep(pace)
        if r.status_code != 200:
            return []
        rows = r.json()
    except (requests.RequestException, json.JSONDecodeError):
        return []
    out = []
    for row in rows[1:]:
        ts, original = row[1], row[2]
        if NON_ARTICLE_URL.search(original):
            continue
        slug = original.rstrip("/").rsplit("/", 1)[-1]
        if len(slug) < 12 or "-" not in slug:
            continue
        out.append((ts, original))
    return out


def fetch_post(ts: str, url: str, pace: float) -> tuple[str, str] | None:
    """Return (title, text) or None."""
    try:
        r = requests.get(f"https://web.archive.org/web/{ts}id_/{url}",
                         headers=UA, timeout=60)
        time.sleep(pace)
        if r.status_code != 200:
            return None
        # pass raw BYTES, not r.text: servers often omit a charset header,
        # requests then defaults to ISO-8859-1 and mangles UTF-8 pages
        # (verified 2026-07-25: corrupted 261/2282 corpus docs). trafilatura
        # sniffs the real encoding from the bytes.
        doc = trafilatura.bare_extraction(r.content, include_comments=False,
                                          with_metadata=True)
        if not doc or not doc.text:
            return None
        return (doc.title or "", doc.text)
    except requests.RequestException:
        return None
    except Exception:
        return None


class GenreClassifier:
    def __init__(self, model: str):
        from google import genai

        # the base GEMINI_API_KEY is not valid for AI Studio (verified
        # 2026-07-21); rotation keys _1.._7 are. Take the first that exists.
        key = next((os.environ[v] for v in
                    [f"GEMINI_API_KEY_{i}" for i in range(1, 8)]
                    + ["GEMINI_API_KEY"] if os.environ.get(v)), None)
        if not key:
            raise SystemExit("no GEMINI_API_KEY_* in environment")
        self.client = genai.Client(api_key=key)
        self.model = model
        self.n_calls = 0

    def classify(self, title: str, text: str) -> str:
        prompt = GENRE_PROMPT.replace("{title}", title[:200]).replace(
            "{text}", " ".join(text.split()[:300]))
        for attempt in range(3):
            try:
                resp = self.client.models.generate_content(
                    model=self.model, contents=prompt)
                self.n_calls += 1
                m = re.search(r'\{[^}]*"genre"\s*:\s*"([a-z_]+)"', resp.text)
                if m:
                    return m.group(1)
            except Exception:
                time.sleep(5 * (attempt + 1))
        return "clf_error"


def heuristic_genre(title: str, slug: str) -> str:
    t = f"{title} {slug.replace('-', ' ')}"
    if NEG_TITLE.search(t):
        return "neg"
    if POS_TITLE.search(t):
        return "pos"
    return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", default="outputs/study_b/qualified_domains.csv")
    parser.add_argument("--limit", type=int, default=0, help="max domains this run")
    parser.add_argument("--per-domain", type=int, default=5)
    parser.add_argument("--model", default="gemini-3-flash-preview")
    parser.add_argument("--pace", type=float, default=4.0)
    parser.add_argument("--seed", type=int, default=202607)
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    posts_path = OUT / "posts.csv"
    dl_path = OUT / "decision_list.csv"

    import pandas as pd

    pool = pd.read_csv(args.pool)
    done: set[str] = set()
    if dl_path.exists():
        done = set(pd.read_csv(dl_path).domain)
    todo = pool[~pool.domain.isin(done)]
    if args.limit:
        todo = todo.head(args.limit)
    print(f"spot-check: {len(todo)} domains to probe "
          f"({len(done)} already done)", file=sys.stderr)

    # frame metadata for the decision list (composite frame optional: the
    # 2026-08 regeneration runs YC-only after the composite lists were lost)
    frames_path = Path("outputs/study_b/frames/composite_frame.csv")
    if frames_path.exists():
        frames = pd.read_csv(frames_path)
        meta = {r.domain: r for _, r in frames.iterrows()}
    else:
        meta = {}
    yc_meta = {}
    ycp = Path("outputs/study_b/yc_all.json")
    if ycp.exists():
        for c in json.loads(ycp.read_text()):
            site = re.sub(r"^https?://", "", (c.get("website") or "").lower())
            d = site.split("/")[0].replace("www.", "")
            if d:
                yc_meta[d] = c

    clf = GenreClassifier(args.model)
    posts_fields = ["domain", "url", "snapshot_ts", "title", "words", "lang",
                    "heuristic", "genre", "usable"]
    dl_fields = ["domain", "company", "stratum", "country", "vertical",
                 "industry_raw", "employees", "n_article_urls",
                 "posts_probed", "posts_en", "posts_informational",
                 "posts_usable", "languages", "est_usable_total",
                 "sample_titles"]
    new_posts = not posts_path.exists()
    new_dl = not dl_path.exists()
    pf = open(posts_path, "a", newline="")
    df_ = open(dl_path, "a", newline="")
    pw = csv.DictWriter(pf, fieldnames=posts_fields)
    dw = csv.DictWriter(df_, fieldnames=dl_fields)
    if new_posts:
        pw.writeheader()
    if new_dl:
        dw.writeheader()

    rng = random.Random(args.seed)
    for i, row in enumerate(todo.itertuples()):
        domain = row.domain
        urls = cdx_article_urls(domain, str(row.best_path or "blog/"), args.pace)
        sample = rng.sample(urls, min(args.per_domain, len(urls)))
        post_rows = []
        for ts, url in sample:
            got = fetch_post(ts, url, args.pace)
            if not got:
                continue
            title, text = got
            words = len(WORD_RE.findall(text))
            lang = detect_lang(text)
            slug = url.rstrip("/").rsplit("/", 1)[-1]
            heur = heuristic_genre(title, slug)
            genre = "n/a"
            if lang == "en" and words >= 300:
                genre = ("news_pr_h" if heur == "neg"
                         else clf.classify(title, text))
            usable = (lang == "en" and words >= 500
                      and genre == "informational")
            post_rows.append({"domain": domain, "url": url, "snapshot_ts": ts,
                              "title": title[:150], "words": words,
                              "lang": lang, "heuristic": heur, "genre": genre,
                              "usable": usable})
        for pr in post_rows:
            pw.writerow(pr)
        pf.flush()

        m = meta.get(domain)
        yc = yc_meta.get(domain)
        n_us = sum(p["usable"] for p in post_rows)
        n_probed = len(post_rows)
        est = (round(n_us / n_probed * row.n_article_urls)
               if n_probed else 0)
        dw.writerow({
            "domain": domain,
            "company": (m.get("company") if m is not None else
                        (yc or {}).get("name", row.company)),
            "stratum": getattr(row, "stratum", "yc") or "yc",
            # v2 composite frame carries region, not country (2026-08-07)
            "country": (m.get("country", m.get("region", "")) if m is not None
                        else "USA"),
            "vertical": row.vertical,
            "industry_raw": (m.get("industry_raw") if m is not None else
                             (yc or {}).get("industry", "")),
            "employees": (m.get("employees", "") if m is not None else
                          (yc or {}).get("team_size", "")),
            "n_article_urls": row.n_article_urls,
            "posts_probed": n_probed,
            "posts_en": sum(p["lang"] == "en" for p in post_rows),
            "posts_informational": sum(
                p["genre"] == "informational" for p in post_rows),
            "posts_usable": n_us,
            "languages": "+".join(sorted({p["lang"] for p in post_rows})),
            "est_usable_total": est,
            "sample_titles": " | ".join(p["title"][:60] for p in post_rows[:3]),
        })
        df_.flush()
        print(f"[{i+1}/{len(todo)}] {domain}: {n_probed} probed, "
              f"{n_us} usable (est total {est})", file=sys.stderr)

    pf.close()
    df_.close()
    print(f"done; genre LLM calls: {clf.n_calls}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
