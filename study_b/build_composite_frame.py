#!/usr/bin/env python
"""Funnel step 1: merge domain frames + deterministic anti-persona category prefilter.

Inputs (whichever exist): outputs/study_b/frames/frame_{inc5000,g2,ft1000}.csv
(contract columns: domain,company,vertical,industry_raw,region,source,list_year)
plus the YC directory dump (outputs/study_b/yc_all.json) via find_domains.yc_frame.

Prefilter rule (published): hard-drop anti-persona categories from metadata -
agencies / marketing consultancies, media & publishers, government / nonprofit /
education institutions. Matching is on industry_raw + company name keywords;
conservative (drop only clear matches; ambiguity survives to the step-2 company-fit screen).

Output: outputs/study_b/frames/composite_frame.csv (also the file spot_check
reads for metadata) + prefilter stats printed. Resume-safe: overwrite is fine,
deterministic given inputs.

  .venv/bin/python -m study_b.build_composite_frame
"""
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FRAMES = Path("outputs/study_b/frames")
OUT = FRAMES / "composite_frame.csv"
COLS = ["domain", "company", "vertical", "industry_raw", "region", "source", "list_year"]

# anti-persona prefilter patterns (industry_raw OR company name; case-insensitive)
DROP = re.compile(
    r"advertis|marketing agenc|media agenc|\bagency\b|\bagencies\b|consultanc|"
    r"public relations|\bpr firm|publish|newspaper|magazine|broadcast|\bmedia\b|"
    r"television|journalism|government|public admin|municipal|federal|nonprofit|"
    r"non-profit|charit|foundation\b|university|college|school district|k-12",
    re.I)
# never drop these even if a DROP word matches (product companies, not agencies)
KEEP_OVERRIDE = re.compile(r"software|saas|platform|app\b|tool|api\b", re.I)


def yc_rows() -> list[dict]:
    try:
        from study_b.find_domains import yc_frame
        rows = yc_frame(Path("outputs/study_b/yc_all.json"))
    except Exception as e:
        print(f"WARN: YC frame unavailable ({e})", file=sys.stderr)
        return []
    out = []
    for r in rows:
        out.append({"domain": r["domain"], "company": r.get("company", ""),
                    "vertical": r.get("vertical", "services_other"),
                    "industry_raw": r.get("industry_raw", r.get("vertical", "")),
                    "region": r.get("region", ""), "source": "yc_directory",
                    "list_year": ""})
    return out


def main() -> int:
    rows: list[dict] = []
    for f in sorted(FRAMES.glob("frame_*.csv")):
        with open(f) as fh:
            n = 0
            for r in csv.DictReader(fh):
                if r.get("domain"):
                    rows.append({c: (r.get(c) or "").strip() for c in COLS})
                    n += 1
            print(f"{f.name}: {n} rows")
    ycs = yc_rows()
    print(f"yc_directory: {len(ycs)} rows")
    rows.extend(ycs)

    # dedupe by domain: earliest-source-first keeps richer frame metadata
    seen: dict[str, dict] = {}
    for r in rows:
        d = r["domain"].lower().removeprefix("www.")
        r["domain"] = d
        if d not in seen:
            seen[d] = r
    merged = list(seen.values())

    kept, dropped = [], []
    for r in merged:
        blob = f"{r['industry_raw']} {r['company']}"
        if DROP.search(blob) and not KEEP_OVERRIDE.search(blob):
            dropped.append(r)
        else:
            kept.append(r)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerows(kept)
    with open(FRAMES / "f1_dropped.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerows(dropped)

    from collections import Counter
    print(f"\nmerged unique domains: {len(merged)}")
    print(f"step-1 prefilter: kept {len(kept)}, dropped {len(dropped)} "
          f"({len(dropped)/max(1,len(merged))*100:.1f}%)")
    print("kept verticals:", dict(Counter(r['vertical'] for r in kept)))
    print("kept sources:", dict(Counter(r['source'] for r in kept)))
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
