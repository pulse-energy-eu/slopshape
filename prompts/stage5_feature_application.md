# Stage 5 feature-application prompt

The single scoring prompt behind all 148,500 main-run answers and the 15,950
rewording-test rescores. Source of truth: the module-level `PROMPT` constant
in study_b/r5_apply.py (the rescoring runner study_b/r7_rescore.py imports
that module, so rescore prompting is byte-identical). This file is a verbatim
copy for readers; the script is authoritative.

Model: gemini-3.6-flash, minimal thinking, one call per (post, dimension)
(aspect mode, 11 calls per post). The post text is placed FIRST so a
document's 11 dimension calls share an identical prefix (implicit caching).

## Prompt template

Placeholders: `{text}` = the post (whitespace-normalized, first 2,600
whitespace-delimited tokens), `{n}` = feature count in the call,
`{dim_note}` = ` of the dimension "<dimension>"` in aspect mode (empty in
single-call mode), `{features}` = the feature block below.

```
You will annotate the B2B blog post below against fixed features.

POST:
{text}

---

Annotate the post above against these {n} features{dim_note}.

Rules:
- Judge only what is in the text.
- Single-choice features (marked ONE): answer with EXACTLY ONE allowed value, verbatim. Never several, never a paraphrase.
- Multi-select features (marked MANY): answer with a JSON list containing every allowed value that applies (may be empty).
- If a feature is genuinely inapplicable, use the closest allowed value (e.g. "none"/"absent" variants) - never invent values, never omit a feature.

FEATURES:
{features}

Return ONLY a JSON object mapping EVERY feature id to its answer, e.g.
{"PUR_JOB_001": "explain", "EVD_MIX_002": ["proprietary data"]}. All {n} ids must be present.
```

## Feature block format

One line per feature, rendered from the frozen instrument
(instrument/condensed_taxonomy_0.85.json; all 266 features are applied -
the style boundary and instrument-floor exclusions are analysis-time):

```
<id> [ONE|MANY]: <question> ALLOWED: <value> | <value> | ...
```

`MANY` for `multi_select` features; `ONE` for binary, categorical, ordinal,
and scale features (forced single verbatim value).
