"""Build the five-stratum composite sampling frame.

Every stratum is a third-party list frozen before ChatGPT (2022-11-30), so
neither companies nor frames could be selected with AI-era knowledge:

  yc          YC directory through W22 (already qualified separately)
  inc5000     Inc. 5000 list 2021 (live JSON API; includes website domains)
  ft1000      FT 1000 Europe 2022 (archived FT table; names -> resolved)
  enterprise  DAX + MDAX + FTSE 100 + CAC 40 constituents, Wikipedia
              snapshots from 2021 (names -> resolved)
  g2          G2 category pages as archived Oct 2021 (product names -> resolved)

Name -> domain resolution uses the Firecrawl search API with a mechanical
rule (first result whose domain is not on the aggregator blocklist, preferring
domains sharing a name token). Resolutions are cached; wrong resolutions get
caught downstream (qualification + spot-check).

Usage:
  .venv/bin/python -m study_b.build_frames --stratum inc5000        # one
  .venv/bin/python -m study_b.build_frames --all                    # all four
  .venv/bin/python -m study_b.build_frames --compose                # merge

Outputs: outputs/study_b/frames/{stratum}.csv and composite_frame.csv
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

OUT = Path("outputs/study_b/frames")
CACHE = OUT / "resolution_cache.json"
UA = {"User-Agent": "sitefire-slop-benchmark/0.1 (research; jochen@sitefire.ai)"}

BLOCKLIST = re.compile(
    r"(wikipedia|linkedin|crunchbase|g2\.com|capterra|facebook|bloomberg|"
    r"ft\.com|inc\.com|reuters|craft\.co|pitchbook|zoominfo|dnb\.com|"
    r"glassdoor|indeed|youtube|twitter|x\.com|instagram|apple\.com|"
    r"play\.google|amazon\.|wsj\.com|forbes|statista|tracxn|owler|"
    r"marketscreener|investing\.com|finance\.yahoo|morningstar|tipranks|"
    r"stockanalysis|simplywall|globenewswire|prnewswire|businesswire)",
    re.IGNORECASE,
)

WAYBACK_SNAPSHOTS = {
    "ft1000": ("20220301043147", "https://www.ft.com/ft1000-2022"),
    "ft1000_2018": ("20180406162631", "https://ig.ft.com/ft-1000/2018/"),
    "dax": ("20210930080600", "https://en.wikipedia.org/wiki/DAX"),
    "mdax": ("20210831075610", "https://en.wikipedia.org/wiki/MDAX"),
    "ftse100": ("20211006134658", "https://en.wikipedia.org/wiki/FTSE_100"),
    "cac40": ("20211021074823", "https://en.wikipedia.org/wiki/CAC_40"),
}

G2_CATEGORIES = {  # category slug -> vertical (2021 snapshots verified)
    "crm": "saas", "marketing-automation": "saas", "e-commerce-platforms":
    "ecommerce", "accounting": "fintech", "payroll": "fintech", "core-hr":
    "saas", "help-desk": "saas", "project-management": "saas",
    "version-control-hosting": "devtools", "cloud-security": "devtools",
    # cycle-2 broadening (snapshots probed 2026-07-22)
    "email-marketing": "saas", "video-conferencing": "saas", "erp": "saas",
    "landing-page-builders": "saas", "survey": "saas",
    "applicant-tracking-systems-ats": "saas", "expense-management": "fintech",
    "contract-management": "saas",
}

VERTICAL_RULES = [  # keyword -> vertical, first match wins
    (r"insur", "insurance"),
    (r"fintech|financial|bank|payment|invest|asset|account|lend|credit|"
     r"capital|wealth|tax\b", "fintech"),
    (r"developer|engineering|devops|infrastructure|cloud|api\b|data|security|"
     r"observab|version control", "devtools"),
    (r"software|saas|it services|it managed|computer|crm|hr\b|human resources|"
     r"marketing automation|help ?desk|project management|productivity",
     "saas"),
    (r"e-?commerce|retail|consumer|fashion|food|beverage|travel|marketplace|"
     r"logistics|delivery", "ecommerce"),
    (r"health|pharma|medic|bio", "health"),
    (r"advertis|marketing|media|agency|consult|staffing|recruit", "services"),
    (r"technology|tech\b|telecom|internet", "saas"),
]

EU_COUNTRIES = {"germany", "france", "uk", "united kingdom", "italy", "spain",
                "netherlands", "sweden", "finland", "denmark", "norway",
                "belgium", "austria", "switzerland", "ireland", "poland",
                "portugal", "lithuania", "latvia", "estonia", "luxembourg",
                "czech republic", "hungary", "romania", "greece", "croatia",
                "slovakia", "slovenia", "bulgaria", "cyprus", "malta"}


def to_vertical(text: str) -> str:
    t = (text or "").lower()
    for pat, v in VERTICAL_RULES:
        if re.search(pat, t):
            return v
    return "other"


_SECOND_LEVEL = {"co", "com", "org", "net", "ac", "gov", "edu"}


def norm_domain(url: str) -> str:
    """Reduce to registered domain (strips www/status/app/blog subdomains)."""
    d = re.sub(r"^https?://", "", (url or "").lower()).split("/")[0].split(":")[0]
    parts = [p for p in d.split(".") if p]
    if len(parts) >= 3 and parts[-2] in _SECOND_LEVEL and len(parts[-1]) <= 3:
        return ".".join(parts[-3:])
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return d


def wayback(ts: str, url: str) -> str:
    last = None
    for backoff in (0, 20, 60):
        if backoff:
            time.sleep(backoff)
        try:
            r = requests.get(f"https://web.archive.org/web/{ts}id_/{url}",
                             headers=UA, timeout=90)
            r.raise_for_status()
            return r.text
        except requests.RequestException as e:
            last = e
    raise last


# ---------------------------------------------------------------- resolution
class Resolver:
    def __init__(self):
        self.key = os.environ.get("FIRECRAWL_API_KEY", "")
        if not self.key:
            raise SystemExit("FIRECRAWL_API_KEY missing; source .env first")
        self.cache: dict[str, str] = (
            json.loads(CACHE.read_text()) if CACHE.exists() else {}
        )
        self.n_calls = 0

    def save(self):
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(self.cache, indent=0, sort_keys=True))

    def resolve(self, company: str, hint: str = "") -> str:
        key = f"{company}|{hint}"
        if key in self.cache:
            return self.cache[key]
        try:
            r = requests.post(
                "https://api.firecrawl.dev/v1/search",
                headers={"Authorization": f"Bearer {self.key}"},
                json={"query": f"{company} {hint} official website", "limit": 5},
                timeout=45,
            )
            r.raise_for_status()
            results = r.json().get("data", [])
        except requests.RequestException:
            results = []
        self.n_calls += 1
        time.sleep(0.6)
        # precision rule: accept only domains sharing a name token (>=4 chars).
        # Companies whose names yield no usable token (e.g. "OCI") are skipped
        # rather than mis-resolved; qualification would not reliably catch a
        # wrong-company domain.
        tokens = {t for t in re.split(r"\W+", company.lower()) if len(t) >= 4}
        best = ""
        for res in results:
            d = norm_domain(res.get("url", ""))
            if not d or BLOCKLIST.search(d):
                continue
            if tokens and any(t in d.replace("-", "") for t in tokens):
                best = d
                break
        self.cache[key] = best
        if self.n_calls % 25 == 0:
            self.save()
        return best


# ------------------------------------------------------------------ fetchers
def fetch_inc5000() -> list[dict]:
    r = requests.get("https://api.inc.com/rest/i5list/2021",
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=120)
    r.raise_for_status()
    rows = []
    for c in r.json()["companies"]:
        d = norm_domain(c.get("website") or "")
        if not d:
            continue
        rows.append({
            "domain": d, "company": c.get("company", ""),
            "vertical": to_vertical(c.get("industry", "")), "region": "us",
            "stratum": "inc5000", "industry_raw": c.get("industry", ""),
            "employees": "", "country": "USA",
            "source_ref": "api.inc.com/rest/i5list/2021 rank "
                          + str(c.get("rank", "")),
        })
    return rows


FT_EDITIONS = {  # edition -> (snapshot key, column indices, employee col)
    "2022": ("ft1000", {"name": 1, "country": 4, "sector": 5, "emp": 10}),
    "2018": ("ft1000_2018", {"name": 2, "country": 3, "sector": 4, "emp": 9}),
}


def fetch_ft1000(resolver: Resolver, limit: int = 0,
                 edition: str = "2022") -> list[dict]:
    snap_key, cols = FT_EDITIONS[edition]
    ts, url = WAYBACK_SNAPSHOTS[snap_key]
    h = wayback(ts, url)
    t = h[h.find("<table"):h.find("</table>")]
    trs = re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.DOTALL)

    def cells(r):
        return [re.sub(r"<[^>]+>", "", c).strip() for c in
                re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.DOTALL)]

    rows = []
    body = trs[1:limit + 1] if limit else trs[1:]
    for i, tr in enumerate(body):
        c = cells(tr)
        if len(c) < 6:
            continue
        rank = c[0]
        name = re.sub(r"[*\u2020]+$", "", c[cols["name"]]).strip()
        country, sector = c[cols["country"]], c[cols["sector"]]
        employees = c[cols["emp"]] if len(c) > cols["emp"] else ""
        d = resolver.resolve(name, country)
        if not d:
            continue
        rows.append({
            "domain": d, "company": name, "vertical": to_vertical(sector),
            "region": "eu" if country.lower() in EU_COUNTRIES else "other",
            "stratum": "ft1000", "industry_raw": sector,
            "employees": employees, "country": country,
            "source_ref": f"FT1000-{edition} rank {rank} ({country}) "
                          f"wayback:{ts}",
        })
        if i % 50 == 0:
            print(f"  ft1000: {i}/{len(body)} resolved", file=sys.stderr)
    return rows


def fetch_enterprise(resolver: Resolver) -> list[dict]:
    import pandas as pd

    rows = []
    for idx_name in ("dax", "mdax", "ftse100", "cac40"):
        ts, url = WAYBACK_SNAPSHOTS[idx_name]
        try:
            tables = pd.read_html(io.StringIO(wayback(ts, url)))
        except Exception as e:
            print(f"  enterprise: {idx_name} failed: {e}", file=sys.stderr)
            continue
        comp = None
        for t in tables:
            cols = [str(c).lower() for c in t.columns]
            if any("company" in c for c in cols) and len(t) >= 20:
                comp = t
                break
        if comp is None:
            print(f"  enterprise: no constituent table in {idx_name}",
                  file=sys.stderr)
            continue
        name_col = [c for c in comp.columns if "company" in str(c).lower()][0]
        sec_cols = [c for c in comp.columns
                    if re.search(r"sector|industry", str(c), re.I)]
        region = "uk" if idx_name == "ftse100" else "eu"
        for _, r in comp.iterrows():
            name = str(r[name_col]).strip()
            if not name or name.lower() == "nan":
                continue
            sector = str(r[sec_cols[0]]) if sec_cols else ""
            d = resolver.resolve(name, "company")
            if not d:
                continue
            rows.append({
                "domain": d, "company": name,
                "vertical": to_vertical(sector),
                "region": "eu" if region != "uk" else "eu",
                "stratum": "enterprise", "industry_raw": sector,
                "employees": "10000+",
                "country": {"dax": "Germany", "mdax": "Germany",
                            "ftse100": "UK", "cac40": "France"}[idx_name],
                "source_ref": f"{idx_name.upper()} constituents "
                              f"wayback:{ts}",
            })
        print(f"  enterprise: {idx_name} done ({len(rows)} total)",
              file=sys.stderr)
    return rows


def fetch_g2(resolver: Resolver, per_category: int = 50) -> list[dict]:
    rows = []
    for slug, vertical in G2_CATEGORIES.items():
        try:
            avail = requests.get(
                "http://archive.org/wayback/available",
                params={"url": f"www.g2.com/categories/{slug}",
                        "timestamp": "20211001"},
                headers=UA, timeout=30).json()
            snap = avail.get("archived_snapshots", {}).get("closest", {})
            if not snap.get("url"):
                print(f"  g2: no snapshot for {slug}", file=sys.stderr)
                continue
            h = wayback(snap["timestamp"], f"https://www.g2.com/categories/{slug}")
        except requests.RequestException as e:
            print(f"  g2: {slug} failed: {e}", file=sys.stderr)
            continue
        # product cards link to /products/{slug}/reviews with a name nearby
        names = re.findall(
            r'href="[^"]*/products/[^"/]+/reviews[^"]*"[^>]*>([^<]{2,60})<',
            h)
        seen: set[str] = set()
        kept = 0
        for name in names:
            name = re.sub(r"\s+", " ", name).strip()
            if not name or name.lower() in seen or len(name) < 3:
                continue
            if re.match(r"^(read more|write a review|learn more|see all)", name,
                        re.I):
                continue
            seen.add(name.lower())
            d = resolver.resolve(name, "software")
            if not d:
                continue
            rows.append({
                "domain": d, "company": name, "vertical": vertical,
                "region": "us", "stratum": "g2", "industry_raw": slug,
                "employees": "", "country": "",
                "source_ref": f"g2/{slug} wayback:{snap['timestamp']}",
            })
            kept += 1
            if kept >= per_category:
                break
        print(f"  g2: {slug} -> {kept} vendors", file=sys.stderr)
    return rows


# ------------------------------------------------------------------ compose
def write_stratum(name: str, rows: list[dict]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.csv"
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["domain", "company", "vertical",
                                          "region", "stratum", "industry_raw",
                                          "employees", "country",
                                          "source_ref"])
        w.writeheader()
        w.writerows(rows)
    print(f"{name}: {len(rows)} rows -> {path}")


def compose() -> None:
    import pandas as pd

    frames = []
    # explicit stratum list: derived files (composite_frame, sweep_frame)
    # must never feed back into composition
    for name in ("inc5000", "ft1000", "ft1000_2018", "enterprise", "g2"):
        f = OUT / f"{name}.csv"
        if f.exists():
            frames.append(pd.read_csv(f))
    df = pd.concat(frames, ignore_index=True)
    # cross-stratum dedupe: a domain keeps its first stratum (priority by
    # rarity: enterprise > ft1000 > g2 > inc5000)
    prio = {"enterprise": 0, "ft1000": 1, "g2": 2, "inc5000": 3, "yc": 4}
    df["_p"] = df.stratum.map(prio).fillna(9)
    df = df.sort_values("_p").drop_duplicates("domain").drop(columns="_p")
    df.to_csv(OUT / "composite_frame.csv", index=False)
    print(f"composite: {len(df)} unique domains -> "
          f"{OUT/'composite_frame.csv'}")
    print(df.groupby("stratum").size().to_string())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stratum",
                        choices=["inc5000", "ft1000", "ft1000_2018",
                                 "enterprise", "g2"])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--compose", action="store_true")
    parser.add_argument("--ft-limit", type=int, default=0,
                        help="debug: only first N FT rows")
    args = parser.parse_args()

    todo = ([args.stratum] if args.stratum
            else ["inc5000", "ft1000", "enterprise", "g2"] if args.all else [])
    resolver = None
    for s in todo:
        if s != "inc5000" and resolver is None:
            resolver = Resolver()
        if s == "inc5000":
            write_stratum(s, fetch_inc5000())
        elif s == "ft1000":
            write_stratum(s, fetch_ft1000(resolver, args.ft_limit))
        elif s == "ft1000_2018":
            write_stratum(s, fetch_ft1000(resolver, args.ft_limit,
                                          edition="2018"))
        elif s == "enterprise":
            write_stratum(s, fetch_enterprise(resolver))
        elif s == "g2":
            write_stratum(s, fetch_g2(resolver))
    if resolver:
        resolver.save()
        print(f"resolver calls this run: {resolver.n_calls}")
    if args.compose or args.all:
        compose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
