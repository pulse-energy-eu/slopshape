"""Domain qualification funnel for the Study B human corpus.

Stage 1 of the corpus builder: find 100-150 ICP-matching domains
whose blogs have enough pre-ChatGPT Wayback coverage to yield 10+ usable posts.

Funnel:
  frame candidates (1000s)  ->  Wayback CDX qualification (cheap, 1-2 req/domain)
                            ->  qualified domains with estimated article counts
                            ->  (later) extraction spot-check + stratified sample

Frames currently implemented:
  - yc: YC directory (yc-oss.github.io), batches through W22, public + versioned.
Further frames (G2/Capterra/Feedspot archived category pages) plug into the
same qualify() step.

Usage:
  .venv/bin/python -m study_b.find_domains --frame yc --sample 80 --seed 42
  .venv/bin/python -m study_b.find_domains --frame yc --all   # full frame, slow

Output: outputs/study_b/domains_{frame}.csv with one row per probed domain:
  domain, vertical, region, n_article_urls, qualified, best_path, error
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

CDX = "https://web.archive.org/cdx/search/cdx"
UA = {"User-Agent": "sitefire-slop-benchmark/0.1 (research; jochen@sitefire.ai)"}
CUTOFF = "20221031"
BLOG_PATHS = ["blog/", "resources/", "articles/", "learn/"]
MIN_ARTICLE_URLS = 25  # need >= this many candidate URLs to expect 10+ usable posts
# Wayback throttles aggressively per IP: pace requests and back off on resets.
BASE_SLEEP = 3.5
BACKOFFS = [20, 60]

# Common Crawl: named immutable snapshots, all provably pre-ChatGPT.
# 2022-49 (Nov/Dec) is deliberately excluded: it straddles the Nov 30 launch.
CC_CRAWLS = ["CC-MAIN-2022-40", "CC-MAIN-2022-33", "CC-MAIN-2022-27",
             "CC-MAIN-2022-21", "CC-MAIN-2022-05"]
CC_INDEX = "https://index.commoncrawl.org/{crawl}-index"
# pywb filter regexes are full-match anchored; inline flags like (?i) 404.
CC_URL_FILTER = "~url:.*(blog|articles|resources|learn|guides|insights).*"
BLOG_SEGMENTS = frozenset(
    {"blog", "articles", "resources", "learn", "guides", "insights"}
)
BLOG_SUBDOMAINS = ("blog.", "articles.", "resources.", "learn.")

SKIP_PAT = re.compile(
    r"/(tag|tags|category|categories|author|page|archive|feed|amp|search)/"
    r"|[?#]|\.(xml|json|jpg|jpeg|png|gif|svg|css|js|pdf)$",
    re.IGNORECASE,
)

# YC batch chronology guard: keep everything up to and including Winter 2022
# (company founded pre-ChatGPT). API format: "Winter 2019", "Summer 2021", ...
def batch_ok(batch: str) -> bool:
    m = re.match(r"^(Winter|Summer|Spring|Fall) (20\d\d)$", batch or "")
    if not m:
        return False
    season, year = m.group(1), int(m.group(2))
    if year < 2022:
        return True
    return year == 2022 and season == "Winter"

VERTICAL_MAP = [
    ("fintech", re.compile(r"fintech|banking|payments|insurance", re.I)),
    ("devtools", re.compile(r"developer|devtool|infrastructure|api|open.?source", re.I)),
    ("ecommerce", re.compile(r"commerce|retail|consumer|marketplace", re.I)),
    ("saas", re.compile(r"b2b|saas|software|productivity|analytics|marketing", re.I)),
]


def yc_frame(path: Path) -> list[dict]:
    cos = json.load(open(path))
    out = []
    for c in cos:
        if not batch_ok(c.get("batch") or ""):
            continue
        # ICP alignment + query cost: drop mega-companies (facebook, airbnb...);
        # ICP is 1-250 employees, 500 leaves headroom for scale-ups.
        team = c.get("team_size")
        if isinstance(team, (int, float)) and team > 500:
            continue
        site = (c.get("website") or "").strip()
        if not site:
            continue
        host = urlparse(site if "//" in site else "https://" + site).netloc.lower()
        host = host.removeprefix("www.")
        if not host or "." not in host:
            continue
        blob = " ".join([c.get("industry") or "", c.get("subindustry") or "",
                         " ".join(c.get("tags") or [])])
        vertical = next((v for v, pat in VERTICAL_MAP if pat.search(blob)), "other")
        region = "eu" if any("europe" in (r or "").lower() for r in c.get("regions") or []) else "us"
        out.append({"domain": host, "vertical": vertical, "region": region,
                    "company": c.get("name"), "batch": c.get("batch")})
    # dedupe by domain, keep first
    seen, deduped = set(), []
    for row in out:
        if row["domain"] in seen:
            continue
        seen.add(row["domain"])
        deduped.append(row)
    return deduped


def cdx_count(domain: str, path: str, timeout: int = 25) -> int:
    """Count distinct pre-cutoff archived article-like URLs under domain/path.
    A path ending in '.' means a subdomain probe (e.g. 'blog.' -> blog.domain/*)."""
    pattern = f"{path}{domain}/*" if path.endswith(".") else f"{domain}/{path}*"
    params = {
        "url": pattern,
        "to": CUTOFF,
        "filter": ["statuscode:200", "mimetype:text/html"],
        "collapse": "urlkey",
        "fl": "original",
        "limit": "400",
        "output": "json",
    }
    r = requests.get(CDX, params=params, headers=UA, timeout=timeout)
    r.raise_for_status()
    if not r.text.strip():
        return 0
    rows = r.json()
    n = 0
    for row in rows[1:]:
        original = row[0]
        if SKIP_PAT.search(original):
            continue
        slug = original.rstrip("/").rsplit("/", 1)[-1]
        if len(slug) >= 12 and "-" in slug:
            n += 1
    return n


def cdx_count_retrying(domain: str, path: str) -> tuple[int, str]:
    """cdx_count with paced retries; returns (count, error). Error only if
    all attempts failed."""
    for backoff in [0, *BACKOFFS]:
        if backoff:
            time.sleep(backoff)
        try:
            n = cdx_count(domain, path)
            time.sleep(BASE_SLEEP + random.uniform(0, 1.5))
            return n, ""
        except requests.RequestException as e:
            err = type(e).__name__
    return 0, err


def qualify_fast(domain: str) -> dict:
    """Cycle-2 fast mode: probe blog/ then the blog. subdomain (together these
    covered 96% of cycle-1 kept domains), plus resources/ only when blog/
    shows a partial signal. Negatives cost 2 probes instead of ~4.4."""
    best_path, best_n = "", 0
    errors = 0
    for path in ("blog/", "blog."):
        n, err = cdx_count_retrying(domain, path)
        if err:
            errors += 1
            if errors >= 2:
                return {"n_article_urls": best_n, "best_path": best_path,
                        "qualified": False, "error": err}
            continue
        if n > best_n:
            best_path, best_n = path, n
        if best_n >= MIN_ARTICLE_URLS:
            return {"n_article_urls": best_n, "best_path": best_path,
                    "qualified": True, "error": ""}
    if 0 < best_n < MIN_ARTICLE_URLS:
        n, err = cdx_count_retrying(domain, "resources/")
        if not err and n > best_n:
            best_path, best_n = "resources/", n
    return {"n_article_urls": best_n, "best_path": best_path,
            "qualified": best_n >= MIN_ARTICLE_URLS, "error": ""}


def qualify(domain: str) -> dict:
    best_path, best_n = "", 0
    errors = 0
    for path in BLOG_PATHS:
        n, err = cdx_count_retrying(domain, path)
        if err:
            errors += 1
            if errors >= 2:  # archive unhappy; stop hammering this domain
                return {"n_article_urls": best_n, "best_path": best_path,
                        "qualified": False, "error": err}
            continue
        if n > best_n:
            best_path, best_n = path, n
        if best_n >= MIN_ARTICLE_URLS:
            break  # qualified; no need to probe further paths
        if path == "blog/" and n == 0:
            # most dead/SPA domains have nothing under any path; one extra
            # probe (resources/) is enough to confirm before giving up
            n2, err2 = cdx_count_retrying(domain, "resources/")
            if not err2 and n2 > best_n:
                best_path, best_n = "resources/", n2
            break
    return {"n_article_urls": best_n, "best_path": best_path,
            "qualified": best_n >= MIN_ARTICLE_URLS, "error": ""}


# ---------------------------------------------------------------------------
# Common Crawl source
# ---------------------------------------------------------------------------

def _cc_article_like(url: str) -> str | None:
    """Return the blog location key if this URL looks like a blog article."""
    if SKIP_PAT.search(url):
        return None
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    host = parsed.netloc.lower()
    segments = [s for s in parsed.path.split("/") if s]
    location = ""
    if any(host.startswith(p) for p in BLOG_SUBDOMAINS):
        location = host.split(".", 1)[0] + "."
    elif segments and segments[0].lower() in BLOG_SEGMENTS:
        location = segments[0].lower() + "/"
    if not location:
        return None
    slug = segments[-1] if segments else ""
    if len(slug) >= 12 and "-" in slug:
        return location
    return None


CC_PROBE_PATHS = ["blog/", "resources/", "articles/", "learn/", "guides/",
                  "insights/"]


def _cc_query(url_pattern: str, crawl: str, timeout: int = 40) -> list[str] | None:
    """One prefix index query (cheap server-side, unlike matchType=domain).
    Returns URL list, or None if all retries failed. The CC index answers
    HTTP 404 for 'no records', which is a valid zero."""
    params = {
        "url": url_pattern,
        "filter": "=status:200",
        "fl": "url",
        "limit": "2000",
        "output": "json",
    }
    for backoff in (0, 10, 30):
        if backoff:
            time.sleep(backoff + random.uniform(0, 5))
        try:
            r = requests.get(CC_INDEX.format(crawl=crawl), params=params,
                             headers=UA, timeout=timeout)
            if r.status_code == 404:
                return []
            r.raise_for_status()
            urls = []
            for line in r.text.strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    urls.append(json.loads(line)["url"])
                except (json.JSONDecodeError, KeyError):
                    continue
            return urls
        except requests.RequestException:
            continue
    return None


def cc_qualify(domain: str, max_queries: int = 14) -> dict:
    """Union article-like URLs across pre-ChatGPT crawls, newest first.

    Query strategy (bounded at max_queries per domain):
    - Newest crawl: probe every known blog path + the blog. subdomain.
    - Later crawls: only re-probe locations that produced articles, falling
      back to blog/-only probing while nothing has been found.
    """
    from collections import Counter

    seen: set[str] = set()
    locations: Counter[str] = Counter()
    crawls_hit: list[str] = []
    failures = queries = 0
    productive: list[str] = []  # url patterns that yielded articles

    def probe(pattern: str, crawl: str) -> bool:
        nonlocal failures, queries
        if queries >= max_queries:
            return False
        queries += 1
        urls = _cc_query(pattern, crawl)
        time.sleep(0.3 + random.uniform(0, 0.3))
        if urls is None:
            failures += 1
            return False
        added = 0
        for u in urls:
            loc = _cc_article_like(u)
            key = u.split("//", 1)[-1].lower().rstrip("/")
            if loc and key not in seen:
                seen.add(key)
                locations[loc] += 1
                added += 1
        if added and pattern not in productive:
            productive.append(pattern)
        return added > 0

    for i, crawl in enumerate(CC_CRAWLS):
        before = len(seen)
        if i == 0:
            patterns = [f"{domain}/{p}*" for p in CC_PROBE_PATHS]
            patterns.append(f"blog.{domain}/*")
        elif productive:
            patterns = list(productive)
        else:
            patterns = [f"{domain}/blog/*", f"blog.{domain}/*"]
        for pattern in patterns:
            probe(pattern, crawl)
            if len(seen) >= MIN_ARTICLE_URLS:
                break
        if len(seen) > before:
            crawls_hit.append(crawl.rsplit("-", 1)[-1])
        if len(seen) >= MIN_ARTICLE_URLS or queries >= max_queries:
            break
        if i >= 1 and not seen:
            break  # nothing in the two most recent crawls: likely dead/SPA
        if failures >= 3 and not seen:
            break
    best_path = locations.most_common(1)[0][0] if locations else ""
    return {"n_article_urls": len(seen), "best_path": best_path,
            "qualified": len(seen) >= MIN_ARTICLE_URLS,
            "error": "CCIndexUnavailable" if failures >= 3 and not seen else "",
            "crawls": "+".join(crawls_hit)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frame", default="yc", choices=["yc", "composite"])
    parser.add_argument("--frame-file", default=None,
                        help="default: yc_all.json for yc, "
                             "frames/composite_frame.csv for composite")
    parser.add_argument("--source", default="wayback", choices=["wayback", "cc"])
    parser.add_argument("--sample", type=int, default=80)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--workers", type=int, default=4,
                        help="cc source only; wayback is always serial")
    parser.add_argument("--domains-file", default=None,
                        help="probe only these domains (one per line); "
                             "metadata joined from the frame where known")
    parser.add_argument("--default-stratum", default="",
                        help="stratum label for domains-file rows not found "
                             "in the frame (e.g. yc for YC target lists)")
    parser.add_argument("--fast-paths", action="store_true",
                        help="wayback only: probe blog/ + blog. subdomain "
                             "(96%% historical coverage) at ~2x speed")
    parser.add_argument("--stop-at-qualified", type=int, default=0,
                        help="stop once this many domains qualified in this "
                             "run (0 = probe everything). With --all --shuffle "
                             "this is an unbiased random sample of the frame.")
    parser.add_argument("--shuffle", action="store_true",
                        help="randomize probe order with --seed (publishable)")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    if args.frame == "composite":
        frame_path = Path(args.frame_file
                          or "outputs/study_b/frames/composite_frame.csv")
        with open(frame_path, newline="") as f:
            frame = []
            seen_domains: set[str] = set()
            for r in csv.DictReader(f):
                d = r["domain"].strip().lower()
                if d and d not in seen_domains:
                    seen_domains.add(d)
                    frame.append({"domain": d, "vertical": r.get("vertical", "other"),
                                  "region": r.get("region", "us"),
                                  "company": r.get("company", ""),
                                  "batch": r.get("stratum", ""),
                                  "stratum": r.get("stratum", "")})
    else:
        frame = yc_frame(Path(args.frame_file or "outputs/study_b/yc_all.json"))
        for r in frame:
            r["stratum"] = "yc"
    print(f"frame '{args.frame}': {len(frame)} candidate domains",
          file=sys.stderr)

    if args.domains_file:
        wanted = [l.strip().lower() for l in open(args.domains_file)
                  if l.strip() and not l.startswith("#")]
        by_domain = {r["domain"]: r for r in frame}
        fallback_stratum = args.default_stratum or "other"
        rows = [by_domain.get(d, {"domain": d, "vertical": "other",
                                  "region": "us", "company": "", "batch": "",
                                  "stratum": fallback_stratum})
                for d in wanted]
        print(f"domains-file: {len(rows)} domains", file=sys.stderr)
    elif not args.all:
        rng = random.Random(args.seed)
        rows = rng.sample(frame, min(args.sample, len(frame)))
        print(f"pilot sample: {len(rows)} domains (seed {args.seed})", file=sys.stderr)
    else:
        rows = list(frame)
        if args.shuffle:
            random.Random(args.seed).shuffle(rows)
            print(f"shuffled frame order (seed {args.seed})", file=sys.stderr)

    suffix = "" if args.source == "wayback" else "_cc"
    outpath = Path(args.out or f"outputs/study_b/domains_{args.frame}{suffix}.csv")
    outpath.parent.mkdir(parents=True, exist_ok=True)
    fields = ["domain", "vertical", "region", "company", "batch", "stratum",
              "n_article_urls", "best_path", "qualified", "error", "crawls"]

    done: set[str] = set()
    prior_q = 0
    if outpath.exists():  # resume: skip clean probes, re-probe errored ones
        with open(outpath, newline="") as f:
            existing = list(csv.DictReader(f))
        # schema migration: if the on-disk header lacks newer columns, rewrite
        # the whole file once so appended rows stay aligned with the header
        on_disk_fields = list(existing[0].keys()) if existing else fields
        if on_disk_fields != fields:
            print(f"migrating {outpath} schema "
                  f"({len(on_disk_fields)} -> {len(fields)} cols)", file=sys.stderr)
            with open(outpath, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
                w.writeheader()
                for r in existing:
                    w.writerow({k: r.get(k, "") for k in fields})
        done = {r["domain"] for r in existing if not (r.get("error") or "").strip()}
        prior_q = len({r["domain"] for r in existing
                       if r.get("qualified") == "True"
                       and not (r.get("error") or "").strip()})
        n_retry = len({r["domain"] for r in existing}) - len(done)
        print(f"resume: {len(done)} clean probes kept ({prior_q} already "
              f"qualified), {n_retry} errored domains will be re-probed",
              file=sys.stderr)
    rows = [r for r in rows if r["domain"] not in done]

    if args.source == "cc":
        qualify_fn = cc_qualify
    else:
        qualify_fn = qualify_fast if args.fast_paths else qualify
    n_q, n_done = prior_q, 0
    write_header = not outpath.exists()
    with open(outpath, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if write_header:
            w.writeheader()

        def emit(row: dict, res: dict) -> None:
            nonlocal n_q, n_done
            n_done += 1
            n_q += res["qualified"]
            w.writerow({**row, "crawls": "", **res})
            f.flush()
            print(f"[{n_done}/{len(rows)}] {row['domain']}: "
                  f"{res['n_article_urls']} urls "
                  f"({'QUALIFIED' if res['qualified'] else 'no'})", file=sys.stderr)

        if args.source == "cc" and args.workers > 1:
            from concurrent.futures import ThreadPoolExecutor, as_completed

            with ThreadPoolExecutor(max_workers=args.workers) as ex:
                futures = {ex.submit(qualify_fn, r["domain"]): r for r in rows}
                for fut in as_completed(futures):
                    emit(futures[fut], fut.result())
        else:
            for row in rows:
                emit(row, qualify_fn(row["domain"]))
                if args.stop_at_qualified and n_q >= args.stop_at_qualified:
                    print(f"stop-at-qualified reached ({n_q})", file=sys.stderr)
                    break

    print(f"\n{n_q}/{len(rows)} qualified "
          f"({100 * n_q / max(len(rows), 1):.0f}%) -> {outpath}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
