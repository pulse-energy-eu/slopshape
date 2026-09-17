# PROVENANCE: frame_g2.csv

Company-domain frame built from **archived G2.com category pages** (Wayback Machine snapshots, 2021-2022). Vendors listed on a 2021/2022 G2 category snapshot demonstrably existed before the Nov-2022 corpus cutoff.

- Retrieval date: 2026-08-07 (run executed evening 2026-08-06 through 2026-08-07, Europe/Berlin)
- Output: `frame_g2.csv` (535 rows, deduped by domain)
- sha256(frame_g2.csv): `6b4ff419f04e3c4e2ebdc2f7783f29d5768f5c4903d2ed5c1f27b772995da5a1`
- All raw HTML, intermediate JSON/JSONL, and the scripts that produced them live in `g2_raw/`.

## Method

1. **Category discovery.** For 30 candidate G2 category slugs, queried the Wayback CDX API
   (`https://web.archive.org/cdx/search/cdx?url=g2.com/categories/<slug>&from=2021&to=2022&filter=statuscode:200`)
   and kept captures with `length > 40000` (smaller captures are archived Cloudflare challenge pages).
   28/30 slugs had usable captures. Full CDX results: `g2_raw/cdx_categories.json`
   (sha256 `3077f15b0b939bcb221c724ab2169894e46f9ffc66d2d48939fe1edb50350525`).
   - No usable snapshots: `cloud-security`, `electronic-health-record-ehr` (dropped).
   - `business-intelligence` snapshots turned out to be a category hub page with no product cards (0 vendors; analytics coverage comes from `data-visualization` + `etl-tools`).
2. **Category page fetch + vendor extraction.** For each category, fetched the raw archived HTML
   (`https://web.archive.org/web/<ts>id_/https://www.g2.com/categories/<slug>`), preferring the latest capture <= 2022-10-31.
   Vendor cards were parsed from `data-event-options` JSON attributes containing `Event::Products::ListItemClicked`
   (carries exact product name + G2 product id) paired with the `/products/<slug>/reviews` href.
   This parse works across both the pre- and post-mid-2022 G2 page markups. 913 cards -> 739 unique product slugs
   (a product appearing in several categories is assigned to the first category in the processing order).
   Archived pagination pages (page >= 2) were probed via CDX prefix queries; none usable, so each category contributes its top ~30-35 listed vendors.
3. **Domain resolution (pass 1).** For each product slug, fetched the nearest archived product page via Wayback's
   redirect (`https://web.archive.org/web/<anchor>id_/https://www.g2.com/products/<slug>/reviews`, anchors
   2022-03-01 / 2021-09-01 / 2021-12-01 / 2022-08-01), skipping archived Cloudflare challenge captures, reading the
   first 700 KB. Extracted the seller-details "Company Website" link (fallback "Website" link) and "HQ Location".
4. **Domain resolution (pass 2).** For pass-1 failures (262 slugs), queried CDX directly (2020-2023, status 200,
   length > 40k), preferred pre-2022-07 captures (stable markup), fetched up to 3 MB (seller section sits past 700 KB
   on long review pages), and applied wider extraction patterns. Recovered 136 additional domains.
   Note: a handful of pass-2 captures fall outside 2021-2022 (2020 or 2023) - these were used ONLY to read the
   vendor's website domain; pre-cutoff existence is established by the 2021/2022 *category* snapshot membership, not the product-page capture date.
5. **Assembly.** Deduped by normalized domain (lowercased, `www.`/`www2.`/`www3.` stripped; host from the archived
   href, wayback-rewrite unwrapped; G2/social/app-store hosts rejected). One row per domain; `industry_raw` = G2
   category name; `vertical` = fixed category->bucket mapping (below); `region` mapped from archived "HQ Location"
   text (us = US state/United States; eu = EU-27 country; other = identifiable non-US/EU; blank = not determinable);
   `list_year` = year of the category snapshot the vendor was extracted from; `source` = `g2.com_wayback`.
   **No domain was guessed or filled from model knowledge or live web search - every domain comes from the archived G2 product page's "Company Website" link. Products whose domain could not be extracted are left out and counted as unresolved.**

## Category snapshots used (all page 1)

| category | capture ts | snapshot URL | cards | local file (g2_raw/) | sha256 |
|---|---|---|---|---|---|
| crm | 20220828100815 | https://web.archive.org/web/20220828100815/https://www.g2.com/categories/crm | 30 | cat_crm_p1_20220828100815.html | 1b51dcc66c040b282e9619ede045358cb1cc327209c47d2cb3a92ecafaa507ff |
| marketing-automation | 20221021205918 | https://web.archive.org/web/20221021205918/https://www.g2.com/categories/marketing-automation | 35 | cat_marketing-automation_p1_20221021205918.html | 14451d5607ca91fe9d139224dcc61d1d0fcd8fbc55f50153a853c0f4fa657f83 |
| email-marketing | 20221031124414 | https://web.archive.org/web/20221031124414/https://www.g2.com/categories/email-marketing | 30 | cat_email-marketing_p1_20221031124414.html | bea6d0ad2ccbb62c93c6b645aec7b4fac4f9a0158f4716e309d4c0ac07083b20 |
| e-commerce-platforms | 20221004031615 | https://web.archive.org/web/20221004031615/https://www.g2.com/categories/e-commerce-platforms | 30 | cat_e-commerce-platforms_p1_20221004031615.html | dd9ebc2339cf5a9a9ad0c8be0cba47d4758d0b758db46bc3cdd19bfee31959a9 |
| payment-gateways | 20220610044523 | https://web.archive.org/web/20220610044523/https://www.g2.com/categories/payment-gateways | 35 | cat_payment-gateways_p1_20220610044523.html | f22ca0080312fb20392ad8da43ef5e472cdc0b36a9ee91419f786a3d58de5874 |
| subscription-billing | 20220812183347 | https://web.archive.org/web/20220812183347/https://www.g2.com/categories/subscription-billing | 30 | cat_subscription-billing_p1_20220812183347.html | 2d285ea6d079c47f476c9a4070016c84c0547a6b029ef197bec00e2e25a9e5b5 |
| billing | 20220607070247 | https://web.archive.org/web/20220607070247/https://www.g2.com/categories/billing | 35 | cat_billing_p1_20220607070247.html | 34c31151412b776d1c988f9d3d8fc9534c9b76a6e3e89a5c24bb8000bb436cbf |
| accounting | 20221009064840 | https://web.archive.org/web/20221009064840/https://www.g2.com/categories/accounting | 35 | cat_accounting_p1_20221009064840.html | 7ee3496117841d99685854f5a53d023894fcae3a8c4bf8fed6d07195184b5c99 |
| insurance-agency-management | 20220126125926 | https://web.archive.org/web/20220126125926/https://www.g2.com/categories/insurance-agency-management | 35 | cat_insurance-agency-management_p1_20220126125926.html | 9379698f4d703beb03f60d93937188b54e56a6d063ac4dfa4f65dbe7a30f60b4 |
| insurance-suites | 20220126124158 | https://web.archive.org/web/20220126124158/https://www.g2.com/categories/insurance-suites | 35 | cat_insurance-suites_p1_20220126124158.html | cebf251a1e5711aa60c0fc78b12c1704bba03b599171e2e9e346011f8a8cb02e |
| core-hr | 20220709231527 | https://web.archive.org/web/20220709231527/https://www.g2.com/categories/core-hr | 35 | cat_core-hr_p1_20220709231527.html | c08cb1249998de1391e8fe25a28c44538cc2221ec8217ca1bd7289c5c4fcd4ca |
| payroll | 20220226053615 | https://web.archive.org/web/20220226053615/https://www.g2.com/categories/payroll | 35 | cat_payroll_p1_20220226053615.html | 00feed3c3739c7c30f39f6890cc7799c0405e921ec133be083328755838ec18a |
| project-management | 20221009052958 | https://web.archive.org/web/20221009052958/https://www.g2.com/categories/project-management | 35 | cat_project-management_p1_20221009052958.html | fd84635d271709df3da10409a4928e1fb7fecb0b6f92031de8d48c27410c5de0 |
| continuous-integration | 20220723090831 | https://web.archive.org/web/20220723090831/https://www.g2.com/categories/continuous-integration | 34 | cat_continuous-integration_p1_20220723090831.html | ed95af596786b1273ee4d2e9f3f769f7023f4453b4938db980022ff62a9f0391 |
| continuous-delivery | 20220126121943 | https://web.archive.org/web/20220126121943/https://www.g2.com/categories/continuous-delivery | 35 | cat_continuous-delivery_p1_20220126121943.html | 4c814e2daa2838a4a16790259b71b529acabd404d9a9803ae1a182065703974c |
| application-performance-monitoring-apm | 20220126123750 | https://web.archive.org/web/20220126123750/https://www.g2.com/categories/application-performance-monitoring-apm | 35 | cat_application-performance-monitoring-apm_p1_20220126123750.html | bcb9486ea8f846fff4351d0ce433389cc7edcdf21c032b9e3ce9465039c1894b |
| identity-and-access-management-iam | 20220126124929 | https://web.archive.org/web/20220126124929/https://www.g2.com/categories/identity-and-access-management-iam | 35 | cat_identity-and-access-management-iam_p1_20220126124929.html | 97220ee8efb039e3ab7b649b358c63a3e7a9705c01d35f78c9308a79743956fa |
| endpoint-protection-suites | 20220816045456 | https://web.archive.org/web/20220816045456/https://www.g2.com/categories/endpoint-protection-suites | 35 | cat_endpoint-protection-suites_p1_20220816045456.html | 449ae2e25b5922ec2b97d030f8355b7e5fdeda7d21ac1ff3d8921dcd18604516 |
| business-intelligence | 20220610071019 | https://web.archive.org/web/20220610071019/https://www.g2.com/categories/business-intelligence | 0 (hub page) | cat_business-intelligence_p1_20220610071019.html | e7ea343b0be39258bd3a0b1dc4dce3e93b61edf71ea662b76f7e9d21ab8134b8 |
| data-visualization | 20220713132335 | https://web.archive.org/web/20220713132335/https://www.g2.com/categories/data-visualization | 35 | cat_data-visualization_p1_20220713132335.html | 0e873e8232def7153c6a2a838ca0dd76ddb26a9501322e7ffbe27f09d8259004 |
| etl-tools | 20220922094311 | https://web.archive.org/web/20220922094311/https://www.g2.com/categories/etl-tools | 35 | cat_etl-tools_p1_20220922094311.html | 5ca0b46598d4423a9e39dcd475ae484b15cb4cb5276f20baa26101b2341b74b3 |
| help-desk | 20220807150033 | https://web.archive.org/web/20220807150033/https://www.g2.com/categories/help-desk | 30 | cat_help-desk_p1_20220807150033.html | 062079f04c900fdfaecdf91a102c21a7a092522881f6c927478ae34d55dcdce1 |
| live-chat | 20220928150839 | https://web.archive.org/web/20220928150839/https://www.g2.com/categories/live-chat | 34 | cat_live-chat_p1_20220928150839.html | e3f956a27f8320d947c0b76cd174b4abf933ef3b68cee9fbfa7e4be3630f3985 |
| learning-management-system-lms | 20211207062658 | https://web.archive.org/web/20211207062658/https://www.g2.com/categories/learning-management-system-lms | 30 | cat_learning-management-system-lms_p1_20211207062658.html | ee2119f8a883faa4c22cc8d499ab4c2bc795f574dd9332c817bb2c1727ad7df8 |
| course-authoring | 20220126124511 | https://web.archive.org/web/20220126124511/https://www.g2.com/categories/course-authoring | 35 | cat_course-authoring_p1_20220126124511.html | 81aac538eae4d6d84795e78b7f56283d5af74aeffa7b5d5a4e6a7b0768f7e338 |
| telemedicine | 20220126132903 | https://web.archive.org/web/20220126132903/https://www.g2.com/categories/telemedicine | 35 | cat_telemedicine_p1_20220126132903.html | a82930f14a6ce2be25222df0c24805770c7972f273dc1ae4955027952521a702 |
| patient-engagement | 20220513102740 | https://web.archive.org/web/20220513102740/https://www.g2.com/categories/patient-engagement | 35 | cat_patient-engagement_p1_20220513102740.html | 98951cf2dd77617efd0e39172131036bb9ce5c2432249e5cf7597f16cc92cb71 |
| applicant-tracking-systems-ats | 20221010222007 | https://web.archive.org/web/20221010222007/https://www.g2.com/categories/applicant-tracking-systems-ats | 35 | cat_applicant-tracking-systems-ats_p1_20221010222007.html | ee744f4d8f72fdc1c2c31c1718f235b45a148e8544f1126e7e6bd061ba1a130e |

Machine-readable manifest: `g2_raw/category_manifest.json` (sha256 `6d5b280244f004b18e3615f5fb53142bc3b672a6242d01a2b647b12735dbe593`).

## Product-page snapshots (per-vendor domain sources)

739 product pages were fetched from Wayback (`https://www.g2.com/products/<slug>/reviews`). The complete per-product record - snapshot capture timestamp, fetched-content sha256, byte count, resolution status, extracted domain - is in:

- `g2_raw/product_snapshots.csv` - sha256 `db9bd36f1726e7f1db530d241c3676fc910dba9c901730fbeebe30651e46093f` (one row per product: URL, capture ts, sha256 of fetched bytes, status, domain)
- `g2_raw/resolved.jsonl` (pass 1 full records) - sha256 `00a9f36d40cfc8ebf81bd5c1922caecc0d56da6bedc28a6170ce7613e899e32b`
- `g2_raw/resolved_pass2.jsonl` (pass 2 full records) - sha256 `284367b0f738c9c41b6bd1bb84b611e82269376151d7ec079a49b76572a7206a`

Product-page HTML was streamed and truncated (700 KB pass 1 / 3 MB pass 2); the recorded sha256 is over the fetched (truncated) bytes, and full HTML bodies were not retained on disk.

## Vertical mapping (category -> bucket)

- software_saas: crm, marketing-automation, email-marketing, core-hr, payroll, project-management, identity-and-access-management-iam, endpoint-protection-suites, data-visualization, help-desk, live-chat, applicant-tracking-systems-ats
- fintech_insurance: payment-gateways, subscription-billing, billing, accounting, insurance-agency-management, insurance-suites
- devtools: continuous-integration, continuous-delivery, application-performance-monitoring-apm, etl-tools
- ecommerce_retail: e-commerce-platforms
- edtech: learning-management-system-lms, course-authoring
- health: telemedicine, patient-engagement
- services_other: (none - all G2 vendors are software companies)

## Results

- 739 unique product slugs -> 613 resolved to a website domain -> **535 unique domains** after dedupe.
- **126 product slugs unresolved** (left out, never guessed): 41 with no usable Wayback capture of the product page, 85 where the archived page had no extractable "Company Website" link (list: `g2_raw/unresolved.json`).
- Vertical distribution: software_saas 253, fintech_insurance 89, devtools 86, edtech 43, health 43, ecommerce_retail 21.
- Region: us 326, other 64, eu 46, blank 99 (blank = HQ Location missing or not confidently mappable).
- list_year: 2022 x 511, 2021 x 24 (all snapshots <= 2022-10-31 except none; all within 2021-01..2022-10).

## Caveats

1. **Top-of-category bias.** Only page 1 of each category was archived (~30-35 vendors, G2's default ranking); no usable archived pagination existed. The frame over-represents G2's better-known vendors per category.
2. **Multi-category vendors** are assigned to the first category processed, so per-category counts are deflated for late-order categories (e.g. insurance-suites: 34/35 of its vendors resolve, but most deduped into earlier categories or share a parent-company domain).
3. **Domain is the seller-details link, verbatim.** A few vendors linked product sub-pages or subdomains (e.g. `app.7taps.com`, `edu.google.com`, `datastudio.withgoogle.com`, `toph.at` for Top Hat); only `www`-prefix stripping was applied, no other rewriting. Big-tech product entries (Apple Pay -> apple.com, GitHub -> github.com) are present and may warrant exclusion downstream depending on ICP filters.
4. **Some pass-2 domain reads used out-of-window captures** (2020 or 2023) when no clean 2021-2022 product-page capture existed; pre-cutoff vendor existence rests on the category snapshot, and the vendor's domain is assumed stable across that gap.
5. `region` is heuristic (string-mapped from archived HQ Location) and blank where ambiguous.
6. `crm` p1 used the 2022-08-28 capture (post-redesign markup); parsing was verified to extract the same card structure across both markups.

## Reproduction

Scripts in `g2_raw/`: `cdx_categories.py` (CDX discovery) -> `fetch_categories.py` (category fetch + card extraction) -> `resolve_products.py` (pass-1 domain resolution) -> `resolve_pass2.py` (pass-2 recovery) -> `build_frame.py` (dedupe + CSV assembly).
