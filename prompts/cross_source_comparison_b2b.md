You are an expert discourse analyst. Below you are given several structured analysis templates. Each template describes a DIFFERENT text, but all of those texts were written from the SAME original prompt shown below. Each template is attributed to an anonymized author label (Author A, Author B, ...).

Your task is NOT to judge which template is better written, and NOT to assess extraction quality. Your task is to identify **systematic differences in the compositional choices** the authors made when writing from the same prompt.

## Instructions

1. Treat each template as evidence about the choices its author made. Differences in content are expected and are exactly what you must characterize.
2. Work dimension by dimension across the material present in the templates: purpose and reader payoff; audience, problem and stakes; structure and flow; explanation depth; evidence and proof; voices and sources; actionability; brand and product integration; timeliness; page format and navigation; and writing style.
3. For each dimension, note concretely how EACH author handled it, then state where the authors diverge.
4. Prefer specific, checkable observations ("Author C resolves via the protagonist's own decision; Authors A and E resolve via an external event") over evaluative statements ("Author C is more sophisticated").
5. Identify patterns that RECUR across this batch - choices that cluster among some authors and are absent in others. These recurring patterns are the most valuable output.
6. Do not speculate about which author is human or machine, and do not treat author labels as evidence of anything beyond the text.

## Output

Return ONLY a JSON object with this schema:

{
  "per_source_dimension_notes": {
    "<Author label>": {
      "<dimension name>": "(string) how this author handled this dimension, concretely"
    }
  },
  "cross_source_divergences": [
    {
      "dimension": "(string) dimension in which authors diverge",
      "axis_of_variation": "(string) the specific compositional choice that varies",
      "by_author": {"<Author label>": "(string) where this author falls on that axis"},
      "notes": "(string) optional detail"
    }
  ],
  "recurring_patterns": [
    {
      "pattern": "(string) a choice that recurs across this batch",
      "authors_exhibiting": ["<Author label>"],
      "authors_not_exhibiting": ["<Author label>"],
      "why_it_matters": "(string) what compositional decision this reflects"
    }
  ],
  "executive_summary": "(string) the most systematic differences observed across this batch"
}
