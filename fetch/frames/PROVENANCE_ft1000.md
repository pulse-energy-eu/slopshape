# PROVENANCE: frame_ft1000.csv

Company-domain frame for the Study B research corpus, built from the FT 1000
(Financial Times "Europe's Fastest Growing Companies") annual ranking,
editions 2020, 2021, and 2022. All three editions were published pre-ChatGPT
(March of their respective year), so listed companies were selected without
AI-era knowledge and their blogs plausibly carry pre-Nov-2022 content.

Retrieval date: 2026-08-07.

## Source snapshots (web.archive.org)

All ranking tables were retrieved as raw archived HTML (`id_` variant) via the
Firecrawl scrape API (Wayback rate-limited direct fetches from this IP on
retrieval day; Firecrawl fetched the identical snapshot URLs from its infra).

| Edition | Original URL | Wayback snapshot | Retrieved via |
|---|---|---|---|
| 2020 | https://www.ft.com/ft1000-2020 | https://web.archive.org/web/20230425220624id_/https://www.ft.com/ft1000-2020 | firecrawl scrape, rawHtml |
| 2021 | https://www.ft.com/content/8b37a92b-15e6-4b9c-8427-315a8b5f4332 ("FT 1000: the fifth annual list") | https://web.archive.org/web/20210331132419id_/https://www.ft.com/content/8b37a92b-15e6-4b9c-8427-315a8b5f4332 | firecrawl scrape, rawHtml |
| 2022 | https://www.ft.com/ft1000-2022 | https://web.archive.org/web/20220301043147id_/https://www.ft.com/ft1000-2022 | firecrawl scrape, rawHtml |

Notes on snapshot choice:
- 2022 snapshot timestamp is the one already pinned in
  `study_b/build_frames.py` (`WAYBACK_SNAPSHOTS["ft1000"]`).
- 2021: the vanity URL ft.com/ft1000-2021 is not archived (Wayback 404); the
  list lives in the article page above, found via web search, snapshot
  resolved by Wayback redirect from `/web/20210401/`.
- 2020: nearest archived snapshot of ft.com/ft1000-2020 is 2023-04-25; the
  page content is the static 2020 ranking table (published 2020-03), identical
  list regardless of snapshot date.

## Raw download hashes (sha256)

Saved under `outputs/study_b/frames/raw_ft1000/`:

```
52c5a4675c68c515e4d628cb15060ccbed9234eb9bb45e42df35284e2cf94c54  ft1000_2020.html (660,889 bytes)
0b5e716d39d1daac2564a905532f5ff6d9345482a81200101ff2e3abe8189e81  ft1000_2021.html (539,880 bytes)
11abe9d7259a8a9ab883e465f52d6fb53ec918cdb0eca0a31854773f0055c1e7  ft1000_2022.html (494,067 bytes)
```

## Extraction

- Each page contains one full ranking table (1000 data rows per edition;
  parsed as largest `<table>` in the HTML). Columns used: Rank (0), Name (1),
  Country (4), FT Category/Sector (5). Trailing `*`/`†` footnote markers
  stripped from names; HTML entities unescaped.
- Sector filter: only in-scope sectors kept (B2B-content-marketing corpus).
  Mapping FT sector -> vertical bucket:
  - software_saas: Technology, Games industry
  - devtools: Cyber Security
  - fintech_insurance: Fintech, Financial Services, Insurance
  - health: Health, Pharmaceuticals ("Healh" typo row in 2020 included)
  - ecommerce_retail: Ecommerce, Retail, Fashion
  - edtech: Education
  - services_other: Support Services, Management Consulting, Advertising,
    Media, Sales & Marketing, Law, Telecoms
  - SKIPPED (out of scope, no resolution attempted): Construction, Industrial
    Goods, Energy, Automobiles, Transport, Food & Beverage, Travel & Leisure,
    Property, Restaurants, Agricultural Commodities, Chemicals, Chemicals &
    Pharmaceuticals, Waste management & recycling, Interiors, Personal &
    Household Goods, Beauty, Batteries, Aerospace & Defence, Architecture,
    Precious metals
- Cross-edition dedupe by normalized company name (lowercase, punctuation and
  common legal suffixes stripped); the latest edition wins and sets
  `list_year`.
- Totals: 3,000 rows parsed -> 1,934 in-scope rows -> 1,572 unique companies
  submitted to domain resolution.

## Domain resolution

- Firecrawl search API, query `"{name} {country} official website"`, limit 5.
- Precision rule (adapted from `study_b/build_frames.py::Resolver`): accept
  the first result whose registered domain (a) is not on the
  aggregator/press/registry blocklist and (b) contains a distinctive name
  token (>= 4 chars, generic tokens like "group"/"consulting"/"services"
  excluded); companies with no distinctive token accepted only on a
  full-name-concatenation match (>= 5 chars). Everything else = unresolved
  (left out of the CSV, counted below) - no guessed domains.
- Domains normalized to registered domain (www/app/blog subdomains stripped,
  ccTLD second-level domains like .co.uk preserved).
- Final dedupe by domain (first occurrence kept; rows sorted latest edition
  first).
- Resolution cache: `raw_ft1000/resolution_cache_ft1000.json` (query ->
  accepted domain, empty string = unresolved).

## Manual QA pass (2026-08-07)

The 31 rows where only a single short (<= 4 chars) name token matched the
domain were audited with targeted web searches. 26 were confirmed correct
(incl. rebrands: Kilo Health -> kilo.co, Samy Road -> samy.com,
Mailtrack -> mailsuite.com). 5 were confirmed WRONG resolutions and dropped
(moved to unresolved):

| Company | Wrongly accepted | Why wrong |
|---|---|---|
| Yoyo Wallet (UK) | yoyofactory.com | yo-yo manufacturer, not the fintech |
| Byte London (UK) | bytes.co.uk | Bytes Technology Group, not the agency (now DEPT) |
| Merk Internethandel (Germany) | merk-blechwarenfabrik.de | different Merk entity |
| Mogo Finance (Latvia) | mogo.ca | Canadian Mogo, not the Latvian lender |
| Link Soluzioni (Italy) | linksfoundation.com | LINKS Foundation, different org |

One additional wrong resolution caught in row eyeballing was corrected rather
than dropped (official domain unambiguous): OnlyFans (UK, 2022) had accepted
the squatter/affiliate domain `only-fans.uk`; replaced with `onlyfans.com`.

## Result

- frame_ft1000.csv rows (unique domains): 1,231
- Unresolved companies (no domain accepted, incl. the 5 QA drops): 279 of
  1,572 (list in `raw_ft1000/unresolved_ft1000.txt`)
- Same-domain duplicates dropped after resolution: 62
- Vertical distribution: software_saas 419, services_other 346,
  ecommerce_retail 231, fintech_insurance 114, health 83, devtools 20,
  edtech 18
- Region: eu 982, uk 249
- Edition (list_year): 2022: 564, 2021: 352, 2020: 315

## Known caveats

- The token-match rule can accept a same-named but wrong company's domain,
  or a country-variant site of the right company (e.g. `.co.uk` instead of
  `.de`). Wrong resolutions are expected to be caught downstream by Wayback
  blog qualification and the spot-check stage.
- Generic-named companies ("Learning Technologies", "Elements ...") carry
  the highest wrong-resolution risk.
- The FT "Technology" category is broad (includes some consumer apps and
  marketplaces); bucketed as software_saas per the frame's category scheme.
- ~2020 edition table lists "FT Category", 2022 lists "Sector"; vocabularies
  are near-identical and were mapped with one table (above).
- Companies renamed/acquired since listing may resolve to their current
  domain rather than the domain they used pre-Nov-2022.
