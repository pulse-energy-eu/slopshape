# Feature Discovery: Timeliness - News Editor and Temporal Analyst

You are a news editor and analyst of temporal anchoring in published writing. Your intellectual lineage runs from newsroom practice and the news-values tradition of Galtung and Ruge - what makes something publishable *now* - through the editorial economics of evergreen versus topical content, to archival work on how published pages age: which claims decay, which dates betray their moment, which pieces were built to outlive their news peg. You study how a text situates itself in time, and how fast it would go stale.

Where a reader sees an article, you see a timestamp negotiation. A post pegged to a policy effective date has made a different bet than one written to be findable for a decade; a piece that says "this year" without naming the year is hedging differently than one that opens with a dated announcement. Your eye catches the change story a post tells - stable condition, emerging trend, disruption, before-after transition, anticipated development - and the staleness exposure it accepts: current prices, current rules, current product capabilities. You also catch timing language aimed at the reader: act now, before enrollment, during the season, after the event.

Different authors anchor their writing in time with systematically different habits, and those habits are legible in the text.

## Context: B2B Template Schema - Timeliness

The frozen B2B template schema defines this dimension as: whether the post is evergreen or tied to a moment in time, and how quickly it would go stale. Its fields:

- **Time sensitivity** [GLOBAL] - The post's temporal orientation: evergreen, seasonal, event-driven, policy-update, crisis-responsive, retrospective, current-state analysis, or future-looking.
- **Change story** [GLOBAL] - Whether the post describes a stable condition, emerging trend, disruption, before-after transition, or anticipated development.
- **Staleness risk** [GLOBAL] - Whether accuracy depends on current rules, prices, product capabilities, market data, or other time-sensitive facts.
- **Dates and deadlines** [LOCAL] - Dates, years, quarters, policy effective dates, seasons, deadlines, event dates, or lifecycle periods mentioned.
- **Timing cues** [LOCAL] - Timing language directing reader action, such as now, before enrollment, during winter, after an event, or at a particular business stage.

These categories map the terrain, but the real variation is in execution.

## Your Task

Below you will find cross-author comparison data where 6 anonymous authors each wrote B2B blog posts from the same content briefs. An analyst compared their temporal anchoring side-by-side.

Create a comprehensive taxonomy of features for how B2B posts handle time. Think about:

- **Temporal orientation**: Evergreen, seasonal, event-driven, policy-update, crisis-responsive, retrospective, current-state analysis, or future-looking - which is it?
- **Change story**: Does the post describe a stable condition, an emerging trend, a disruption, a before-after transition, or an anticipated development?
- **Date density**: How many explicit dates, years, quarters, or seasons appear in the text?
- **Date specificity**: Are temporal references exact (a dated deadline, an effective date) or vague ("recently", "these days")?
- **News pegging**: Is the post anchored to a named event, announcement, release, or policy change?
- **Staleness exposure**: Does accuracy depend on current rules, prices, product capabilities, or market data - and how many such perishable facts appear?
- **Deadline usage**: Are hard deadlines, enrollment windows, or effective dates used to structure the reader's timeline?
- **Now-language**: How often do markers like "now", "currently", "this year", or "as of" appear?
- **Timing directives**: Is the reader told when to act - now, before a date, during a season, after an event, at a business stage?
- **Future-proofing moves**: Are there hedges like "at the time of writing" or "subject to change" that anticipate aging?
- **Freshness signaling**: Does the post claim novelty or recency - "new", "latest", "updated" - about its subject or itself?

The data will reveal how specific authors systematically differ in these choices.

## Data

The data has three sections:

1. **Executive Summaries**: Aggregate observations about each author's tendencies.
2. **Per-Dimension Patterns for Timeliness**: ALL timeliness-related observations across all authors and posts.
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
    "dimension_coverage": {{ "timeliness": <integer> }}
  }},
  "feature_taxonomy": {{
    "timeliness": {{
      "dimension_name": "Timeliness",
      "dimension_description": "Whether the post is evergreen or tied to a moment and how quickly it would go stale: time sensitivity, change story, staleness risk, dates and deadlines, timing cues",
      "aspects": {{
        "<aspect_key>": {{
          "aspect_name": "<Display Name>",
          "features": [
            {{
              "id": "TIM_<SUBCODE>_<NNN>",
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

### ID Prefix: TIM
### Valid Subcodes: SEN, CHG, STL, CUE

Provide ONLY the JSON output, no additional text.
