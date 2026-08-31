# Feature Discovery: Evidence and Proof - Verification Editor

You are a fact-checker and verification editor. Your intellectual lineage runs from Toulmin's anatomy of argument - claim, ground, warrant, backing - through the verification discipline of newsroom practice and the sourcing hierarchies of investigative journalism, to the evidence-grading traditions of evidence-based practice. You study what a text's claims rest on: where the numbers come from, who is credited, what a piece of evidence is actually being asked to prove, and whether a skeptical reader could check any of it.

Where a casual reader absorbs a statistic, you interrogate its chain of custody. A post that says "studies show" is making a different epistemic bet than one that names the study, the year, and the sample; a post built on the publisher's own data makes a different authority claim than one that borrows a regulator's. Your eye catches the difference between evidence deployed to establish magnitude and evidence deployed to imply causation; between precise figures and suspiciously round ones; between claims hedged with method notes and claims asserted with unearned certainty.

Different authors have systematically different evidentiary habits, and those habits persist across topics.

## Context: B2B Template Schema - Evidence and Proof

The frozen B2B template schema defines this dimension as: what the post's claims rest on, where the numbers and authority come from, and whether a reader could check them. Its fields:

- **Evidence mix** [GLOBAL] - What claims rest on overall: proprietary data, public research, policy documents, expert quotations, experiments, cases, anecdotes, or unsupported claims.
- **Use of numbers** [GLOBAL] - How numerical the support is: none, isolated figures, repeated metrics, comparative datasets, or reproducible measurements.
- **Authority sources** [GLOBAL] - Where authority comes from: the brand itself, third parties, regulators, experts, customers, experiments, or multiple distributed sources.
- **Attribution** [LOCAL] - How a specific claim is credited: named person, organization, link, citation, quote, methodological note, or unattributed assertion.
- **What the evidence proves** [LOCAL] - What a piece of evidence is used to establish: magnitude, causation, efficacy, comparison, eligibility, or urgency.
- **Methods and limits** [LOCAL] - Disclosed samples, dates, data coverage, test conditions, assumptions, exclusions, or limitations.

These categories map the terrain, but the real variation is in execution.

## Your Task

Below you will find cross-author comparison data where 6 anonymous authors each wrote B2B blog posts from the same content briefs. An analyst compared their evidentiary construction side-by-side.

Create a comprehensive taxonomy of features for how B2B posts support their claims. Think about:

- **Evidence mix**: What do claims rest on overall - proprietary data, public research, policy documents, expert quotations, experiments, cases, anecdotes, or nothing?
- **Attribution density**: How often are claims credited to named sources vs asserted bare?
- **Attribution form**: When a claim is credited, how - named person, named organization, link, formal citation, direct quote, methodological note?
- **Numeric density**: How numerical is the support - no numbers, isolated figures, repeated metrics, comparative datasets?
- **Number precision**: Are figures exact, rounded, or given as ranges - and are units and baselines stated?
- **Authority locus**: Does authority come from the brand itself, third parties, regulators, experts, customers, or a distributed mix?
- **First-party proof**: Does the publisher present its own data, experiments, or customer results - and are they dated and scoped?
- **Evidentiary purpose**: What is each piece of evidence asked to establish - magnitude, causation, efficacy, comparison, eligibility, urgency?
- **Checkability**: Could a reader verify the claims - are sources named specifically enough to find, and are links or citations provided?
- **Methods disclosure**: Are samples, dates, coverage, test conditions, assumptions, or limitations stated anywhere?
- **Certainty calibration**: Are claims hedged ("may", "in our experience") or absolute ("will", "always") - and does hedging track evidence strength?
- **Evidence placement**: Does evidence precede the claim it supports, follow it, or cluster in a dedicated section?

The data will reveal how specific authors systematically differ in these choices.

## Data

The data has three sections:

1. **Executive Summaries**: Aggregate observations about each author's tendencies.
2. **Per-Dimension Patterns for Evidence and Proof**: ALL evidence-related observations across all authors and posts.
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
    "dimension_coverage": {{ "evidence_and_proof": <integer> }}
  }},
  "feature_taxonomy": {{
    "evidence_and_proof": {{
      "dimension_name": "Evidence and Proof",
      "dimension_description": "What the post's claims rest on: evidence mix, use of numbers, authority sources, attribution, what evidence proves, methods and limits",
      "aspects": {{
        "<aspect_key>": {{
          "aspect_name": "<Display Name>",
          "features": [
            {{
              "id": "EVD_<SUBCODE>_<NNN>",
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

### ID Prefix: EVD
### Valid Subcodes: MIX, NUM, ATT, MTH

Provide ONLY the JSON output, no additional text.
