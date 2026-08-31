"""Final domain selection + human-corpus fetch.

Two subcommands:

  select   Apply the documented mechanical quota rules to the keep-eligible
           pool -> corpus_domains_selected.csv. Rules (published):
           - all non-saas keep-eligible domains enter;
           - saas is capped so it is <=40% of the final corpus, ranked by
             verified yield (posts_usable desc, est_usable_total desc,
             domain alphabetical as deterministic tiebreak).

  fetch    For each selected domain: list archived article URLs (Wayback CDX,
           pre 2022-11-30), seeded-sample up to --candidates (15), fetch each
           snapshot, apply the verified filter chain (English, 600-2,500
           words, informational genre via heuristic + Gemini Flash, minhash
           dedup), keep at most --keep (12), drop domains netting < 3.
           Resume-safe per domain. Outputs:
             outputs/study_b/corpus/story_human.parquet   (the frozen corpus)
             outputs/study_b/corpus/ledger.csv            (provenance)

Usage:
  .venv/bin/python -m study_b.build_corpus select
  .venv/bin/python -m study_b.build_corpus fetch [--limit N] [--pace 3.5]
"""

from __future__ import annotations

import argparse
import hashlib
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from study_b.spot_check import (  # noqa: E402
    GenreClassifier, WORD_RE, cdx_article_urls, detect_lang, fetch_post,
    heuristic_genre,
)

OUT = Path("outputs/study_b/corpus")
SEED = 202607
SAAS_CAP = 0.40
MIN_WORDS, MAX_WORDS = 600, 2500
MIN_KEEP = 3


def cmd_select() -> int:
    import pandas as pd

    k = pd.read_csv("outputs/study_b/spotcheck/decision_list_kept.csv")
    non_saas = k[k.vertical != "saas"]
    saas = k[k.vertical == "saas"].sort_values(
        ["posts_usable", "est_usable_total", "domain"],
        ascending=[False, False, True])
    # saas <= SAAS_CAP of final: n_s <= cap/(1-cap) * n_non
    max_saas = int(SAAS_CAP / (1 - SAAS_CAP) * len(non_saas))
    sel = pd.concat([non_saas, saas.head(max_saas)])
    OUT.mkdir(parents=True, exist_ok=True)
    sel.to_csv(OUT / "corpus_domains_selected.csv", index=False)
    print(f"selected {len(sel)} domains "
          f"({len(non_saas)} non-saas + {min(max_saas, len(saas))} saas, "
          f"saas share {min(max_saas, len(saas))/len(sel)*100:.0f}%)")
    print(sel.stratum.value_counts().to_string())
    return 0


def _shingles(text: str, n: int = 5) -> set[int]:
    toks = [t.lower() for t in WORD_RE.findall(text)][:1200]
    return {hash(" ".join(toks[i:i + n])) for i in range(len(toks) - n + 1)}


def cmd_fetch(args) -> int:
    import csv as csvmod
    import json

    import pandas as pd

    sel = pd.read_csv(OUT / "corpus_domains_selected.csv")
    ledger_path = OUT / "ledger.csv"
    done: set[str] = set()
    if ledger_path.exists():
        done = set(pd.read_csv(ledger_path).domain)
    todo = sel[~sel.domain.isin(done)]
    if args.limit:
        todo = todo.head(args.limit)
    print(f"fetch: {len(todo)} domains to go ({len(done)} done)",
          file=sys.stderr)

    # efficiency: reuse spot-check evidence. Known-usable URLs are fetched
    # first (only the text is missing; genre verdict is reused, no LLM call).
    # Known-bad URLs are excluded from sampling entirely.
    url_cache: dict[str, dict] = {}
    scp = Path("outputs/study_b/spotcheck/posts.csv")
    if scp.exists():
        for r in pd.read_csv(scp).itertuples():
            url_cache[str(r.url).rstrip("/")] = {
                "usable": bool(r.usable), "genre": str(r.genre),
                "lang": str(r.lang)}
    # efficiency: one CDX query on the domain's known best path
    bp = pd.read_csv("outputs/study_b/qualified_domains.csv")[
        ["domain", "best_path"]].drop_duplicates("domain")
    best_path = dict(zip(bp.domain, bp.best_path.fillna("blog/")))

    clf = GenreClassifier(args.model)
    rng = random.Random(SEED)
    ledger_fields = ["domain", "stratum", "vertical", "doc_id", "url",
                     "wayback_url", "snapshot_ts", "title", "words", "genre",
                     "kept", "drop_reason"]
    new_ledger = not ledger_path.exists()
    lf = open(ledger_path, "a", newline="")
    lw = csvmod.DictWriter(lf, fieldnames=ledger_fields)
    if new_ledger:
        lw.writeheader()

    docs_path = OUT / "corpus_docs.jsonl"  # crash-safe incremental store
    df_docs = open(docs_path, "a")
    for i, row in enumerate(todo.itertuples()):
        if clf.n_calls > args.max_llm_calls:
            print(f"FATAL: LLM call cap {args.max_llm_calls} exceeded; "
                  "aborting for cost safety", file=sys.stderr)
            return 2
        path = str(best_path.get(row.domain, "blog/") or "blog/")
        urls = cdx_article_urls(row.domain, path, args.pace)
        if len(urls) < args.candidates and path != "blog.":
            urls += cdx_article_urls(row.domain, "blog.", args.pace)
        seen_urls = set()
        known_good, fresh = [], []
        for ts, u in urls:
            key = u.split("//", 1)[-1].lower().rstrip("/")
            if key in seen_urls:
                continue
            seen_urls.add(key)
            cached = url_cache.get(u.rstrip("/"))
            if cached is None:
                fresh.append((ts, u))
            elif cached["usable"]:
                known_good.append((ts, u))
            # known-bad: skip entirely
        rng.shuffle(fresh)
        sample = (known_good + fresh)[:args.candidates]
        kept, sh_seen = 0, []
        for ts, url in sample:
            if kept >= args.keep:
                break
            got = fetch_post(ts, url, args.pace)
            entry = {"domain": row.domain, "stratum": row.stratum,
                     "vertical": row.vertical, "url": url,
                     "wayback_url": f"https://web.archive.org/web/{ts}/{url}",
                     "snapshot_ts": ts, "kept": False}
            if not got:
                lw.writerow({**entry, "doc_id": "", "title": "", "words": 0,
                             "genre": "", "drop_reason": "fetch_or_extract"})
                continue
            title, text = got
            words = len(WORD_RE.findall(text))
            entry.update({"title": title[:150], "words": words})
            if detect_lang(text) != "en":
                lw.writerow({**entry, "doc_id": "", "genre": "",
                             "drop_reason": "language"})
                continue
            if not (MIN_WORDS <= words <= MAX_WORDS):
                lw.writerow({**entry, "doc_id": "", "genre": "",
                             "drop_reason": "length"})
                continue
            slug = url.rstrip("/").rsplit("/", 1)[-1]
            cached = url_cache.get(url.rstrip("/"))
            if cached is not None and cached["usable"]:
                genre = "informational"  # verified by spot-check, no LLM call
            else:
                heur = heuristic_genre(title, slug)
                genre = ("news_pr_h" if heur == "neg"
                         else clf.classify(title, text))
            if genre != "informational":
                lw.writerow({**entry, "doc_id": "", "genre": genre,
                             "drop_reason": "genre"})
                continue
            sh = _shingles(text)
            if any(len(sh & s) / max(len(sh | s), 1) > 0.5 for s in sh_seen):
                lw.writerow({**entry, "doc_id": "", "genre": genre,
                             "drop_reason": "near_duplicate"})
                continue
            sh_seen.append(sh)
            doc_id = hashlib.sha1(f"{row.domain}|{url}".encode()).hexdigest()[:16]
            lw.writerow({**entry, "doc_id": doc_id, "genre": genre,
                         "kept": True, "drop_reason": ""})
            df_docs.write(json.dumps({
                "doc_id": doc_id, "domain": row.domain,
                "stratum": row.stratum, "vertical": row.vertical,
                "title": title, "story_human": text, "words": words,
                "snapshot_ts": str(ts), "url": url,
            }) + "\n")
            kept += 1
        lf.flush()
        df_docs.flush()
        print(f"[{i+1}/{len(todo)}] {row.domain}: {kept} kept "
              f"of {len(sample)} sampled", file=sys.stderr)

    lf.close()
    df_docs.close()
    compact()
    print(f"genre LLM calls this run: {clf.n_calls}", file=sys.stderr)
    return 0


def compact() -> None:
    """corpus_docs.jsonl -> story_human.parquet (dedup by doc_id, keep last).
    Safe to run anytime; the jsonl remains the crash-safe source of truth."""
    import json

    import pandas as pd

    docs_path = OUT / "corpus_docs.jsonl"
    if not docs_path.exists():
        return
    rows = [json.loads(l) for l in open(docs_path) if l.strip()]
    if not rows:
        return
    df = pd.DataFrame(rows).drop_duplicates("doc_id", keep="last")
    df.to_parquet(OUT / "story_human.parquet", index=False)
    print(f"corpus: {len(df)} posts, {df.domain.nunique()} domains -> "
          f"{OUT/'story_human.parquet'}", file=sys.stderr)


def cmd_retry(args) -> int:
    """Re-fetch URLs that failed with fetch_or_extract (Wayback throttling),
    at gentler pacing, for domains still below the keep cap. Appends to the
    same ledger/jsonl; last row per URL wins at analysis time."""
    import csv as csvmod
    import json

    import pandas as pd

    led = pd.read_csv(OUT / "ledger.csv")
    last = led.drop_duplicates("wayback_url", keep="last")
    kept_per_domain = led[led.kept.astype(bool)].groupby("domain").size()
    cand = last[last.drop_reason.isin(
        ["fetch_or_extract", "fetch_or_extract_retry"])]
    cand = cand[cand.domain.map(lambda d: kept_per_domain.get(d, 0)) < args.keep]
    if args.limit:
        cand = cand.head(args.limit)
    print(f"retry: {len(cand)} failed URLs across "
          f"{cand.domain.nunique()} domains", file=sys.stderr)

    # shingle sets of already-kept posts per domain (dedup continuity)
    dom_sh: dict[str, list] = {}
    docs_path = OUT / "corpus_docs.jsonl"
    if docs_path.exists():
        for line in open(docs_path):
            if line.strip():
                d = json.loads(line)
                dom_sh.setdefault(d["domain"], []).append(
                    _shingles(d["story_human"]))

    url_cache: dict[str, dict] = {}
    scp = Path("outputs/study_b/spotcheck/posts.csv")
    if scp.exists():
        for r in pd.read_csv(scp).itertuples():
            url_cache[str(r.url).rstrip("/")] = {"usable": bool(r.usable)}

    clf = GenreClassifier(args.model)
    ledger_fields = ["domain", "stratum", "vertical", "doc_id", "url",
                     "wayback_url", "snapshot_ts", "title", "words", "genre",
                     "kept", "drop_reason"]
    lf = open(OUT / "ledger.csv", "a", newline="")
    lw = csvmod.DictWriter(lf, fieldnames=ledger_fields)
    df_docs = open(docs_path, "a")
    kept_now: dict[str, int] = dict(kept_per_domain)
    n_ok = 0
    for i, r in enumerate(cand.itertuples()):
        if clf.n_calls > args.max_llm_calls:
            print("FATAL: LLM cap exceeded", file=sys.stderr)
            return 2
        if kept_now.get(r.domain, 0) >= args.keep:
            continue
        got = fetch_post(str(r.snapshot_ts), r.url, args.pace)
        entry = {"domain": r.domain, "stratum": r.stratum,
                 "vertical": r.vertical, "url": r.url,
                 "wayback_url": r.wayback_url, "snapshot_ts": r.snapshot_ts,
                 "kept": False}
        if not got:
            lw.writerow({**entry, "doc_id": "", "title": "", "words": 0,
                         "genre": "", "drop_reason": "fetch_or_extract_retry"})
            continue
        title, text = got
        words = len(WORD_RE.findall(text))
        entry.update({"title": title[:150], "words": words})
        if detect_lang(text) != "en":
            lw.writerow({**entry, "doc_id": "", "genre": "",
                         "drop_reason": "language"})
            continue
        if not (MIN_WORDS <= words <= MAX_WORDS):
            lw.writerow({**entry, "doc_id": "", "genre": "",
                         "drop_reason": "length"})
            continue
        cached = url_cache.get(str(r.url).rstrip("/"))
        if cached is not None and cached["usable"]:
            genre = "informational"
        else:
            heur = heuristic_genre(title, str(r.url).rsplit("/", 1)[-1])
            genre = ("news_pr_h" if heur == "neg"
                     else clf.classify(title, text))
        if genre != "informational":
            lw.writerow({**entry, "doc_id": "", "genre": genre,
                         "drop_reason": "genre"})
            continue
        sh = _shingles(text)
        sh_list = dom_sh.setdefault(r.domain, [])
        if any(len(sh & s) / max(len(sh | s), 1) > 0.5 for s in sh_list):
            lw.writerow({**entry, "doc_id": "", "genre": genre,
                         "drop_reason": "near_duplicate"})
            continue
        sh_list.append(sh)
        doc_id = hashlib.sha1(f"{r.domain}|{r.url}".encode()).hexdigest()[:16]
        lw.writerow({**entry, "doc_id": doc_id, "genre": genre,
                     "kept": True, "drop_reason": ""})
        df_docs.write(json.dumps({
            "doc_id": doc_id, "domain": r.domain, "stratum": r.stratum,
            "vertical": r.vertical, "title": title, "story_human": text,
            "words": words, "snapshot_ts": str(r.snapshot_ts),
            "url": r.url}) + "\n")
        kept_now[r.domain] = kept_now.get(r.domain, 0) + 1
        n_ok += 1
        if i % 25 == 0:
            lf.flush(); df_docs.flush()
            print(f"[{i}/{len(cand)}] recovered {n_ok} so far",
                  file=sys.stderr)
    lf.close(); df_docs.close()
    compact()
    print(f"retry done: recovered {n_ok} posts; LLM calls {clf.n_calls}",
          file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("select")
    pf = sub.add_parser("fetch")
    pf.add_argument("--limit", type=int, default=0)
    pf.add_argument("--candidates", type=int, default=15)
    pf.add_argument("--keep", type=int, default=12)
    pf.add_argument("--pace", type=float, default=3.0)
    pf.add_argument("--model", default="gemini-3-flash-preview")
    pf.add_argument("--max-llm-calls", type=int, default=6000,
                    help="hard cost-safety cap for genre calls per run")
    pr = sub.add_parser("retry-failures")
    pr.add_argument("--limit", type=int, default=0)
    pr.add_argument("--keep", type=int, default=12)
    pr.add_argument("--pace", type=float, default=5.0)
    pr.add_argument("--model", default="gemini-3-flash-preview")
    pr.add_argument("--max-llm-calls", type=int, default=6000)
    args = parser.parse_args()
    if args.cmd == "select":
        return cmd_select()
    if args.cmd == "retry-failures":
        return cmd_retry(args)
    return cmd_fetch(args)


if __name__ == "__main__":
    sys.exit(main())
