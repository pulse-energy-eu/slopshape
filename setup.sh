#!/usr/bin/env bash
# Idempotent environment bootstrap for the SlopShape release package.
# Creates the virtualenv, clones the two pinned upstream repositories, and
# applies the released fork patch (artifacts/our-fork.patch) to the vendored
# StoryScope pipeline. Rerun safely at any time.
set -euo pipefail
cd "$(dirname "$0")"

STORYSCOPE_COMMIT=642e746804e1ee4138ffdcf13b7412eb3dc2a70b
EXCESS_COMMIT=53db991afc251782106cd817a1c3fa47a4d41781

echo "== venv (Python 3.12; 3.14 breaks shap/numba resolution) =="
if [ ! -x .venv/bin/python ]; then
  if command -v uv >/dev/null 2>&1; then
    uv venv --python 3.12 .venv
  else
    python3.12 -m venv .venv
  fi
fi
if command -v uv >/dev/null 2>&1; then
  uv pip install -p .venv/bin/python -r requirements.txt
else
  .venv/bin/pip install -r requirements.txt
fi

echo "== vendored upstream repos (pinned) =="
mkdir -p vendor data outputs
if [ ! -d vendor/storyscope/.git ]; then
  git clone https://github.com/jenna-russell/storyscope vendor/storyscope
fi
git -C vendor/storyscope fetch --quiet origin "$STORYSCOPE_COMMIT" 2>/dev/null || true
git -C vendor/storyscope checkout --quiet "$STORYSCOPE_COMMIT" 2>/dev/null \
  || { echo "FAIL: storyscope pin $STORYSCOPE_COMMIT not found upstream; a rebuild"; \
       echo "      against a different upstream state is a new measurement, not a"; \
       echo "      verification (README.md, model availability caveat)."; exit 1; }

echo "== fork patch (the study's declared deviations from upstream) =="
if git -C vendor/storyscope diff --quiet "$STORYSCOPE_COMMIT" -- storyscope config; then
  git -C vendor/storyscope apply ../../artifacts/our-fork.patch
  echo "applied artifacts/our-fork.patch"
else
  echo "working clone already carries deviations; run"
  echo "  .venv/bin/python -m study_b.verify_reference"
  echo "to check they match the released patch."
fi

echo "== B2B discovery prompts into the vendored prompts dir =="
# study_b/r3_discover_b2b.py swaps these in; vendor code itself is unmodified
cp prompts/aspect_b2b_*.md vendor/storyscope/storyscope/prompts/

if [ ! -d vendor/llm-excess-vocab/.git ]; then
  git clone https://github.com/berenslab/llm-excess-vocab vendor/llm-excess-vocab
fi
git -C vendor/llm-excess-vocab fetch --quiet origin "$EXCESS_COMMIT" 2>/dev/null || true
git -C vendor/llm-excess-vocab checkout --quiet "$EXCESS_COMMIT" 2>/dev/null \
  || echo "WARN: llm-excess-vocab pin $EXCESS_COMMIT not found; staying on $(git -C vendor/llm-excess-vocab rev-parse --short HEAD)"

cp vendor/llm-excess-vocab/results/excess_words.csv data/excess_words.csv

echo "== smoke test =="
.venv/bin/python - <<'PY'
import pandas as pd, xgboost, shap, sklearn, trafilatura, openai, anthropic
from google import genai
import csv
rows = list(csv.DictReader(open("data/excess_words.csv")))
style = [r for r in rows if r["type"] == "style"]
assert len(rows) == 900 and len(style) == 407, (len(rows), len(style))
print(f"OK: deps import; excess words {len(rows)} ({len(style)} style)")
PY

echo "== drift check =="
.venv/bin/python -m study_b.verify_reference

echo "== API keys (only needed for the LLM stages; analysis stages need none) =="
if [ -f .env ]; then
  set -a; source .env; set +a
fi
missing=0
for k in OPENAI_API_KEY ANTHROPIC_API_KEY GEMINI_API_KEY AI_GATEWAY_API_KEY; do
  if [ -z "${!k:-}" ]; then echo "not set: $k (copy env.example to .env and fill; names in env.example)"; missing=1; fi
done
[ "$missing" = 0 ] && echo "All generation-stage keys present."

echo "Done. See code/README.md for the stage map."
