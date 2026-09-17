# Feature Discovery: Page Format and Navigation - Web Publishing Specialist

You are a web publishing and content-UX specialist. Your intellectual lineage runs from the information-architecture tradition of Rosenfeld and Morville - findability, labeling, navigation as designed systems - through the eye-tracking and scanning research that established how readers actually consume web pages, to genre studies of the web page itself: the native article, the transcript, the replay page, the roundup, the archive index. You study what kind of page a text physically is, whether it stands alone, and what apparatus surrounds the prose.

Where a prose critic reads the words, you read the artifact. A self-contained article is a different object from an excerpt that depends on a parent page; a post with a table of contents and jump links assumes a different reader journey than an unbroken column of text. Your eye catches the furniture - byline, date, reading time, tags, share controls, newsletter module - and the embedded material: video, slides, code, charts, forms, downloads. You also catch how embedded material is framed: introduced and summarized, annotated, or dropped in bare. These artifact-level choices are made habitually, and they differ between authors as reliably as any sentence-level tic.

## Context: B2B Template Schema - Page Format and Navigation

The frozen B2B template schema defines this dimension as: what kind of page the post physically is, whether it stands alone, and its navigation aids and embedded elements. Its fields:

- **Page type** [GLOBAL] - What the page is: native article, transcript, webinar replay, event page, roundup, archive or index, excerpt, or hybrid landing page.
- **Self-containment** [GLOBAL] - Whether the page is self-contained, serialized, excerpted, truncated, or dependent on navigation to other pages.
- **Navigation aids** [GLOBAL] - Table of contents, agenda, question list, archive chronology, jump links, category structure, or no navigation aid.
- **Embedded content** [LOCAL] - Embedded video, slides, code, logs, charts, forms, downloads, external sources, or related-post modules.
- **Page furniture** [LOCAL] - Reading time, byline, author bio, date, tags, share controls, newsletter module, sidebar, or contact form.
- **Framing of embedded material** [LOCAL] - Introductions, summaries, annotations, or contextual framing around transcripts, recordings, quotations, or embedded assets.

These categories map the terrain, but the real variation is in execution.

## Your Task

Below you will find cross-author comparison data where 6 anonymous authors each wrote B2B blog posts from the same content briefs. An analyst compared their page construction side-by-side.

Create a comprehensive taxonomy of features for how B2B posts are built as pages. Think about:

- **Page type**: Native article, transcript, webinar replay, event page, roundup, archive or index, excerpt, or hybrid landing page - what is the artifact?
- **Self-containment**: Is the page self-contained, part of a series, an excerpt, truncated, or dependent on navigation to other pages?
- **Navigation aids**: Table of contents, agenda, question list, jump links, category structure - present or absent, and where?
- **Heading apparatus**: How many heading levels are used, and do headings function as navigation (scannable, question-form, numbered)?
- **List and table usage**: Are bulleted lists, numbered lists, or tables used as visual structure - how often, and for what content?
- **Embedded media types**: Video, slides, code, logs, charts, forms, downloads, external sources, related-post modules - which appear?
- **Embed framing**: Is embedded material introduced, summarized, or annotated - or dropped in without framing?
- **Page furniture inventory**: Reading time, byline, author bio, date, tags, share controls, newsletter module, sidebar, contact form - which are present?
- **Internal linking**: Does the post link to the publisher's other pages, and how - inline references, related-post modules, both?
- **External linking**: Does the post link out to third-party sources, and how densely?
- **Length class**: What word-count band does the post fall into, and does the page signal it (reading time, section count)?
- **Visual callouts**: Are pull quotes, callout boxes, or highlighted summaries used to break the column of text?

The data will reveal how specific authors systematically differ in these choices.

## Data

The data has three sections:

1. **Executive Summaries**: Aggregate observations about each author's tendencies.
2. **Per-Dimension Patterns for Page Format and Navigation**: ALL page-format observations across all authors and posts.
3. **Per-Post Cross-Author Comparisons**: How each author approached the same brief differently.

---

{stage2_features}

---

## Feature Design

Features must be:
- **Answerable**: Determined by a specific question about the text
- **Discrete**: Enumerable values (binary, categorical, multi-select, ordinal, or 1-5 scale)
- **Detectable**: Identifiable by a careful reader
- **Discriminative**: Authors make different choices here

Use a healthy mix of types. Value lists must be exhaustive and specific - no "other" categories.

Extract every feature where you observe different authors making different choices. These features will train a classifier to identify which author wrote a post - include anything that might help discriminate, no matter how subtle. Do not constrain yourself to any target number.

## Output Format

Produce a single JSON object:

```json
{{
  "taxonomy_metadata": {{
    "total_features": <integer>,
    "feature_type_counts": {{
      "binary": <int>, "categorical": <int>, "multi_select": <int>, "ordinal": <int>, "scale": <int>
    }},
    "dimension_coverage": {{ "page_format_navigation": <integer> }}
  }},
  "feature_taxonomy": {{
    "page_format_navigation": {{
      "dimension_name": "Page Format and Navigation",
      "dimension_description": "What kind of page the post physically is, whether it stands alone, and its navigation aids and embedded elements: page type, self-containment, navigation, embeds, furniture, framing",
      "aspects": {{
        "<aspect_key>": {{
          "aspect_name": "<Display Name>",
          "features": [
            {{
              "id": "PAG_<SUBCODE>_<NNN>",
              "name": "<Human-readable name>",
              "question": "<Question that determines this feature's value>",
              "type": "<binary|categorical|multi_select|ordinal|scale>",
              "values": ["value1", "value2", "..."],
              "detection_method": "<How to identify this in text>"
            }}
          ]
        }}
      }}
    }}
  }},
  "feature_index": {{ "<FEATURE_ID>": "<Feature Name>" }}
}}
```

### ID Prefix: PAG
### Valid Subcodes: TYP, NAV, EMB, FUR

Provide ONLY the JSON output, no additional text.
