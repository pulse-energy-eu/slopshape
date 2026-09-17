<!--
LAMP rewording-attack prompt (R7 durability harness).

Grounding: Chakrabarty, Laban & Wu, "Can AI writing be salvaged? Mitigating
Idiosyncrasies and Improving Human-AI Alignment in the Writing Process through
Edits" (arXiv 2409.14509). Their formative study with professional writers
formalized a seven-category taxonomy of undesirable idiosyncrasies in LLM text;
the LAMP corpus applies span-level edits targeting exactly these categories.
The original study (its section 8.3) used it as its durability test:
span-level rewriting of the 7 categories, Gemini stories with Gemini as its
own rewriter. Here every model rewrites ITS OWN posts.

Deliberate deviations from LAMP as published:
- NO fiction few-shot examples (LAMP ships 25 professional fiction edit
  examples; our domain is nonfiction B2B web content - domain mismatch).
- NO instruction about document structure in either direction (headings,
  lists, formatting): the attack must be the natural LAMP-style edit,
  neither protecting nor targeting structure.

Prompt-iteration log (pilot, 2026-08-30):
- v1: seven categories + hard constraints only. Pilot (10 posts): length,
  refusal, and claim gates passed, but the trivial-copy gate flagged 3/10
  (deepseek 2, claude 1; deepseek returned near-identical text, 0.99
  13-gram overlap - it treated "leave clean spans alone" as license to skip
  the edit).
- v2: added the "artifacts are pervasive / near-identical output means the
  edit was not performed / reword in fresh phrasing" paragraph. Fixed claude
  (0.72 mean overlap) and gpt; deepseek still returned verbatim copies (1.0
  and 0.976 overlap). Separately, kimi truncated one rewrite mid-sentence
  (7,037 reasoning tokens ate the 8,000-token cap - code fix, cap now
  16,000), and gemini dropped two concrete examples and substituted a new
  reason in one rewrite (claim-check "no").
- v3: two additions, no other changes. (1) "Only a sentence that exhibits
  none..." sentence, aimed at deepseek's no-op behavior. (2) Hard constraint
  extended with "and every concrete example. Do not swap an example, cause,
  or reason for a different one", aimed at gemini's substitution. This is
  the version below (final).
- Two harness-level fixes landed alongside v3 (code, not prompt):
  a system message for all providers - load-bearing for deepseek, which
  no-ops without one - and an in-loop trivial-copy retry guard (deepseek
  still no-ops nondeterministically WITH the system message). Final pilot
  under v3 + both fixes: 0 length violations (ratios 0.82-1.00), 0 copy
  flags, 0 refusals, claim preservation 8/10 (two borderline single-item
  misses; pilot and full-run gate record in artifacts/r7/GATES.md).

Placeholder: {POST} is replaced with the full original post text.
-->

You are editing a blog post you previously wrote. Professional editors have identified seven categories of writing artifacts that commonly degrade AI-drafted prose. Go through the post span by span; wherever a span exhibits one of these artifacts, rewrite that span. Leave spans that are already clean.

The seven artifact categories:

1. Cliche: overused phrases and stock expressions that have lost their impact through repetition.
2. Unnecessary/redundant exposition: excessive or repeated information that restates the obvious or re-explains what the reader already got; telling what has already been shown.
3. Purple prose: overly ornate wording, sprawling sentences, and stacked adjectives that add flourish without adding meaning.
4. Poor sentence structure: constructions that reduce clarity and readability - weak transitions, run-ons, and needlessly complex sentences.
5. Lack of specificity and detail: vague generalizations where a concrete, contextual detail would let the reader see the point.
6. Awkward word choice and phrasing: misused or disproportionate words, unclear pronoun references, excessive passive voice.
7. Tense inconsistency: unmotivated shifts between past, present, and future that muddy the timeline.

These artifacts are pervasive in AI-drafted posts: expect to find and rewrite many spans throughout the post, not just one or two. When you rewrite a span, reword it in genuinely fresh phrasing - do not keep the original sentence with a single word swapped. Only a sentence that exhibits none of the seven artifacts may stay verbatim, and in a typical AI draft such sentences are the minority. Returning the post unchanged or nearly unchanged means the edit was not performed and is a failed response.

Hard constraints:

- Preserve every factual claim, number, statistic, name, product, quotation, link, and every concrete example. Do not add any new fact, figure, example, source, or claim, and do not swap an example, cause, or reason for a different one.
- Preserve the post's meaning, intent, and audience.
- Edit spans; do not summarize, condense the post overall, or expand it with new material. The rewritten post should cover exactly what the original covers.

Output the full rewritten post only - no preamble, no commentary, no list of edits.

The post:

{POST}
