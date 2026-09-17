"""Anti-quotation ablation, step 1: briefs WITHOUT clause 7, all else identical.
Reviewer condition on Dev 5b. Uses the first 200 tranche prompts (dev surface,
never the holdout) so the arm is paired against the existing corrected-brief
tranche. The ONLY change is removing the anti-quotation rule and renumbering."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from study_b import extract_briefs as eb

RULE7 = """7. Do NOT quote or closely paraphrase distinctive sentences, statistics, or \\
anecdotes. A writer working only from this brief must not be able to \\
reconstruct its wording.
8. Single paragraph <= 120 words."""
RULE7_PLAIN = RULE7.replace("\\\n", "")
# the module string has no backslash-newlines after parsing; rebuild from the live value
old = eb.BRIEF_PROMPT
import re
new = re.sub(r"7\. Do NOT quote.*?reconstruct its wording\.\s*\n8\.", "7.", old, flags=re.S)
assert new != old and "Do NOT quote" not in new, "clause 7 removal failed"
eb.BRIEF_PROMPT = new
print("clause 7 removed; rule 8 renumbered to 7", file=sys.stderr)

if __name__ == "__main__":
    sys.argv = ["noaq_briefs",
                "--doc-ids", "outputs/study_b/pipeline/noaq_ids.txt",
                "--out", "outputs/study_b/corpus/briefs_noaq.jsonl",
                "--concurrency", "10"]
    sys.exit(eb.main())
