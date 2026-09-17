# Provenance: frame_inc5000.csv

Company-domain frame built from the Inc. 5000 lists (Inc. magazine's annual ranking of the fastest-growing private US companies), vintages 2019-2022.

Retrieval date: 2026-08-07 (retrieved evening of 2026-08-06 local time, Europe/Berlin).

## Sources

All data comes from Inc.'s own public list API, fetched live (no Wayback fallback needed). One JSON document per list year:

| URL | List year | Companies in payload | sha256 (raw JSON as downloaded) |
| --- | --- | --- | --- |
| https://api.inc.com/rest/i5list/2019 | 2019 | 5,010 | 0518c72c457bc3e9484158fa4c8f2f21a4f2d911ff0c99e71b27bf4ce822904b |
| https://api.inc.com/rest/i5list/2020 | 2020 | 5,003 | 03e777fcf10cca5916c70c78eb233ae92264da2ce40698898090d55fce0f6d7f |
| https://api.inc.com/rest/i5list/2021 | 2021 | 4,998 | 8bc7c6b5d61177d8d2c44961b50eb40f0850d23c2faa715af9c8b2c5d8e21873 |
| https://api.inc.com/rest/i5list/2022 | 2022 | 4,992 | 61b42e7bb66f6e5debe458fb4fcdac5a91718371d0666c1b3c0bf61a214627d3 |

The API endpoint was located via public references to it (R fetch script for the 2022 list: https://gist.github.com/MattSandy/14242b5af9dce69102647e2000848bcc). It is the same backend that powers the inc.com/inc5000 list pages.

Raw JSON payloads are archived gzipped next to this file in `raw_inc5000/` (`api_{year}.json.gz`). The sha256 values above are of the uncompressed JSON exactly as downloaded (`shasum -a 256`).

## What was extracted

Per company record: `rank`-year (as `list_year`), `company`, `website` (normalized to bare host: lowercase, scheme/path/query stripped, leading `www.` stripped), `industry` (Inc.'s own category string, kept verbatim in `industry_raw`).

## Processing

1. Parsed all four JSON files (19,966 usable records of 20,003; 37 dropped for missing/invalid website values that did not normalize to a valid hostname).
2. Mapped Inc. industry categories to the study's vertical buckets:
   - software_saas: Software; Artificial Intelligence & Data
   - fintech_insurance: Financial Services; Insurance; Crypto & Blockchain; Economic/Financial Equity
   - health: Health Services; Healthcare & Medical; Health Products; Biotech
   - ecommerce_retail: Retail; E-Commerce; Consumer Products; Food & Beverage
   - edtech: Education
   - devtools: (no Inc. category maps here; bucket is empty in this frame)
   - services_other: everything else (Business Products & Services, IT Services, Advertising & Marketing, Construction, Real Estate, Logistics & Transportation, Government Services, Manufacturing, Human Resources, Telecommunications, Energy, Security, Engineering, Environmental Services, Consumer Services, Travel & Hospitality, Media, Legal, Computer Hardware, Automotive, Sports, Agriculture & Natural Resources, Arts & Entertainment, Corporate Services, Not-for-Profit, and small variants)
3. Deduplicated by normalized domain, keeping the EARLIEST list-year occurrence (earliest vintage best supports the pre-Nov-2022 content requirement).
4. Removed 3 rows whose "website" was a social/platform page rather than a company domain (facebook.com, youtube.com, one business.site page).
5. `region` set to `us` for all rows: the Inc. 5000 is by definition a ranking of US-based private companies.

## Output

- `frame_inc5000.csv`: 11,675 rows (unique domains), columns `domain,company,vertical,industry_raw,region,source,list_year`.
- sha256 of final CSV: 4bb33d3a51cae7cc9d4f2d02c7c17ccc510c735e4d0f1f08169b8314e138b2b1

## Caveats

- devtools bucket is empty: Inc.'s taxonomy has no developer-tools category; devtools-type companies on the list sit inside "Software" (mapped to software_saas) or "IT Services" (services_other).
- The 2019 list uses a slightly older schema ("Legacy list") but carries the same core fields.
- `list_year` is the earliest Inc. 5000 vintage in 2019-2022 in which the domain appeared, not necessarily its only appearance (companies recurring across years are collapsed to one row).
- All companies existed for years before their list year (Inc. eligibility requires a multi-year revenue history), so even 2022-vintage rows predate Nov 2022 by a wide margin; blog existence pre-Nov-2022 still needs per-domain verification downstream.
- Websites are as self-reported to Inc. at list time; some domains may have since lapsed, redirected, or been acquired.
