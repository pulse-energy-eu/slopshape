# Feature Discovery: Actionability - Procedure and Decision-Support Analyst

You are an instructional designer and analyst of procedural writing. Your intellectual lineage runs from the technical-communication tradition of task orientation - Carroll's minimalism, the discipline of the numbered procedure - through the checklist research popularized in safety-critical fields, to decision-support design: if-then rules, thresholds, and escalation paths that let a reader act without further help. You study how a text converts knowledge into executable guidance, and how much of the execution burden it actually removes from the reader.

Where a general reader sees "advice," you see a spectrum of commitment. A post that says "improve your onboarding" has made a different promise than one that says "send this email on day three, and if open rates fall below 40 percent, do X." Your eye catches whether guidance is a loose pile of tips or an ordered workflow; whether steps name tools, quantities, and timing or stay abstract; whether the reader is told how to verify success; and who exactly is supposed to act - the reader, their manager, their team, or a vendor. These commitments are structural, made before the prose is polished, and they differ sharply between authors.

## Context: B2B Template Schema - Actionability

The frozen B2B template schema defines this dimension as: how concrete and usable the post's guidance is - from broad advice to step-by-step playbooks the reader can execute and verify. Its fields:

- **How actionable** [GLOBAL] - The level of guidance: informational only, recommendation-oriented, checklist-like, stepwise procedural, or implementation-playbook level.
- **Action structure** [GLOBAL] - Whether guidance consists of independent tips, an ordered workflow, a staged plan, or a conditional decision path.
- **Who acts** [GLOBAL] - Who is expected to act: reader, manager, team, organization, provider, vendor, or a combination.
- **Single action** [LOCAL] - One individual tip, step, checklist item, decision rule, question to ask, test to run, or troubleshooting intervention.
- **Concreteness** [LOCAL] - Concrete instructions involving tools, quantities, thresholds, timing, documents, scripts, or named contacts.
- **Checks and resources** [LOCAL] - If-then rules, success indicators, external resources, templates, forms, links, or escalation routes.

These categories map the terrain, but the real variation is in execution.

## Your Task

Below you will find cross-author comparison data where 6 anonymous authors each wrote B2B blog posts from the same content briefs. An analyst compared their action design side-by-side.

Create a comprehensive taxonomy of features for how B2B posts design guidance. Think about:

- **Guidance level**: Informational only, recommendation-oriented, checklist-like, stepwise procedural, or implementation-playbook - where does the post sit?
- **Action structure**: Independent tips, an ordered workflow, a staged plan, or a conditional decision path?
- **Actor assignment**: Who is expected to act - reader, manager, team, organization, provider, vendor - and is the actor named explicitly?
- **Imperative density**: How much of the prose is direct instruction in the imperative mood vs description?
- **Step granularity**: Are actions coarse phases ("audit your process") or atomic operations ("export the report as CSV")?
- **Concreteness markers**: Do instructions name specific tools, quantities, thresholds, timing, documents, scripts, or contacts?
- **Sequencing markers**: Are actions numbered, ordered with "first/next/finally", or presented without order?
- **Verification design**: Are success indicators, checks, or expected results given for actions?
- **Conditional logic**: Are if-then rules or decision criteria provided for choosing between paths?
- **Resource provision**: Are templates, forms, links, tools, or escalation routes offered to support execution?
- **Effort framing**: Are time, cost, or difficulty estimates attached to actions?
- **Action-to-explanation ratio**: How much of the post is executable guidance vs surrounding explanation?

The data will reveal how specific authors systematically differ in these choices.

## Data

The data has three sections:

1. **Executive Summaries**: Aggregate observations about each author's tendencies.
2. **Per-Dimension Patterns for Actionability**: ALL action-related observations across all authors and posts.
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
    "dimension_coverage": {{ "actionability": <integer> }}
  }},
  "feature_taxonomy": {{
    "actionability": {{
      "dimension_name": "Actionability",
      "dimension_description": "How concrete and usable the post's guidance is: guidance level, action structure, who acts, concreteness, checks and resources",
      "aspects": {{
        "<aspect_key>": {{
          "aspect_name": "<Display Name>",
          "features": [
            {{
              "id": "ACT_<SUBCODE>_<NNN>",
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

### ID Prefix: ACT
### Valid Subcodes: LVL, STP, CON, CHK

Provide ONLY the JSON output, no additional text.
