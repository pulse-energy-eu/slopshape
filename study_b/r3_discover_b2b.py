#!/usr/bin/env python
"""Stage-4 discovery driver with the B2B dimension set (D11).

Imports the vendored discover_features module and swaps DIMENSION_PROMPTS to
the 11 B2B aspect prompts (frozen schema artifacts/TEMPLATE_SCHEMA_V2.md)
before delegating to its main(). Vendor code is not modified; the B2B prompt
files are ADDED alongside the originals in the vendored prompts dir.

  .venv/bin/python -m study_b.r3_discover_b2b --comparisons-dir ... --output-dir ... [--runs 3]
"""
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "vendor/storyscope"))

B2B_DIMENSION_PROMPTS = {
    "purpose_reader_payoff": "aspect_b2b_purpose.md",
    "audience_problem_stakes": "aspect_b2b_audience.md",
    "structure_and_flow": "aspect_b2b_structure.md",
    "explanation_depth": "aspect_b2b_explanation.md",
    "evidence_and_proof": "aspect_b2b_evidence.md",
    "voices_and_sources": "aspect_b2b_voices.md",
    "actionability": "aspect_b2b_actionability.md",
    "brand_product_integration": "aspect_b2b_commercial.md",
    "timeliness": "aspect_b2b_timeliness.md",
    "page_format_navigation": "aspect_b2b_pageformat.md",
    "writing_style": "aspect_b2b_style.md",
}


def main() -> int:
    mod = importlib.import_module(
        "storyscope.4_feature_discovery.discover_features")
    missing = [f for f in B2B_DIMENSION_PROMPTS.values()
               if not (ROOT / "vendor/storyscope/storyscope/prompts" / f).exists()]
    if missing:
        raise SystemExit(f"B2B aspect prompts missing: {missing}")
    mod.DIMENSION_PROMPTS.clear()
    mod.DIMENSION_PROMPTS.update(B2B_DIMENSION_PROMPTS)
    mod.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
