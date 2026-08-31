#!/bin/bash
# R3 - feature discovery. Launch AFTER the widened
# corpus is frozen and templated. Est ~$210 (terra) incl. answerability screen
# and the template-vs-direct ablation (~$90).
#
# D1: pool select + export (templates + raw ablation variant)
# D2: stage-3 cross-source comparison (terra high, batches of 3, resume-safe)
# D3: stage-4 discovery 3 runs x 11 B2B dimensions (terra, b2b prompt override)
# D4: union taxonomy -> answerability screen (strict 2-vote) -> dedup cluster
#     (F2LLM-4B, threshold via outcome-blind sweep, default 0.85)
# D5: ablation leg - same compare+discover (1 run) on RAW texts
#
# Resume-safe throughout; rerun to continue. STOPS (no spend) unless corpus
# is frozen, templates cover it fully, and balance >= $250.
set -u
cd "$(dirname "$0")/.."
PY=.venv/bin/python
LOG=outputs/study_b/r3.log
STATUS=outputs/study_b/R3_STATUS
R3=outputs/study_b/r3
CFG=vendor/storyscope/config/models.yaml
say()  { echo "[$(date +%F' '%H:%M:%S)] $*" | tee -a "$LOG"; }
stat_() { echo "$*" > "$STATUS"; }
kill_tree() { local p; for p in $(pgrep -P "$1" 2>/dev/null); do kill_tree "$p"; done; kill "$1" 2>/dev/null; }
CHILD=""
trap '[ -n "$CHILD" ] && kill_tree "$CHILD"; say "STOPPED (signal)"; stat_ "stopped"; exit 130' INT TERM

# ---------- gates ------------------------------------------------------------
mkdir -p outputs/study_b
set -a; source .env; set +a
[ -n "${AI_GATEWAY_API_KEY:-}" ] || { say "ABORT: keys missing"; exit 1; }
BAL=$($PY -c "
import sys; sys.path.insert(0,'.')
from study_b.generate_mirrors import gateway_balance
b = gateway_balance(); print(f'{b:.0f}' if b is not None else 'NA')")
say "R3: gateway balance \$$BAL"
[ "$BAL" != "NA" ] && [ "${BAL%.*}" -ge 250 ] || { say "ABORT: balance < \$250"; stat_ "aborted: balance"; exit 1; }
# composition gate (no directional spend on a corpus that came out wrong):
# widened corpus must be >=1900 docs with the YC share
# mechanically diluted (<0.58); else STOP before any discovery spend.
$PY - <<'EOF' || { say "STOP: widened corpus composition off-target - PI review before discovery spend"; stat_ "stopped: composition"; exit 1; }
import pandas as pd
h = pd.read_parquet("outputs/study_b/corpus/story_human_frozen.parquet")
yc = (h.stratum.str.contains("yc", case=False, na=False)).mean()
print(f"composition gate: {len(h)} docs, YC share {yc:.3f}")
assert len(h) >= 1900, f"only {len(h)} docs (< 1900)"
assert yc < 0.58, f"YC share {yc:.3f} not diluted (< 0.58 required)"
EOF
# corpus/template coverage gate: every frozen doc must have 6 templates
$PY - <<'EOF' || { say "ABORT: templates do not fully cover the frozen corpus - finish R2 first"; stat_ "aborted: coverage"; exit 1; }
import json
import pandas as pd
h = set(pd.read_parquet("outputs/study_b/corpus/story_human_frozen.parquet").doc_id)
from collections import Counter
c = Counter()
for l in open("outputs/study_b/templates/templates_v2.jsonl"):
    r = json.loads(l)
    if "template" in r and r["doc_id"] in h:
        c[r["doc_id"]] += 1
full = sum(1 for d in h if c[d] == 6)
print(f"template coverage: {full}/{len(h)} docs with all 6 sources")
assert full == len(h), f"{len(h)-full} docs missing templates"
EOF
say "=== R3 discovery starting ==="

# B2B prompts: canonical tracked copies live in study_b/prompts_b2b (vendor/ is
# gitignored - the 2026-08-01 lesson); sync them into the vendored prompt dir.
/bin/cp study_b/prompts_b2b/*.md vendor/storyscope/storyscope/prompts/
say "synced $(ls study_b/prompts_b2b/*.md | wc -l | tr -d ' ') B2B prompt files into vendor"

( while true; do sleep 600
    NB=$(ls "$R3"/comparisons/stage2_batch_*_analysis.json 2>/dev/null | wc -l | tr -d ' ')
    NR=$(ls -d "$R3"/discovery/run_* 2>/dev/null | wc -l | tr -d ' ')
    echo "r3 heartbeat $(date +%H:%M) | compare batches ${NB:-0} | discovery runs ${NR:-0}" >> "$STATUS"
  done ) & HB=$!
trap '[ -n "$CHILD" ] && kill_tree "$CHILD"; kill $HB 2>/dev/null; say "STOPPED (signal)"; stat_ "stopped"; exit 130' INT TERM
trap 'kill $HB 2>/dev/null' EXIT

# ---------- D1 pool + export -------------------------------------------------
stat_ "D1 pool/export"
( $PY -m study_b.r3_pipeline_input --n-docs 100 --raw ) >> "$LOG" 2>&1 & CHILD=$!; wait $CHILD; CHILD=""
[ -s "$R3/discovery_pool.json" ] || { say "ABORT: pool selection failed"; stat_ "failed: D1"; exit 2; }
say "D1 done: pool $(python3 -c "import json; print(json.load(open('$R3/discovery_pool.json'))['n'])") docs"

# ---------- D2 cross-source comparison --------------------------------------
stat_ "D2 comparison"
( $PY -c "
import sys
sys.path.insert(0, 'vendor/storyscope')
import importlib
mod = importlib.import_module('storyscope.3_cross_source_comparison.compare_sources')
mod.load_comparison_prompt = lambda: (__import__('pathlib').Path('vendor/storyscope/storyscope/prompts/cross_source_comparison_b2b.md')).read_text(encoding='utf-8')
sys.argv = ['compare_sources', '--templates-dir', '$R3/templates',
            '--output-dir', '$R3/comparisons', '--config', '$CFG',
            '--parallel', '4', '--batch-size', '3', '--resume']
mod.main()" ) >> "$LOG" 2>&1 & CHILD=$!; wait $CHILD; CHILD=""
NB=$(ls "$R3"/comparisons/stage2_batch_*_analysis.json 2>/dev/null | wc -l | tr -d ' ')
say "D2 done: $NB comparison batches"
[ "$NB" -ge 30 ] || { say "STOP: too few comparison batches ($NB)"; stat_ "stopped: D2 $NB"; exit 3; }

# ---------- D3 discovery 3x --------------------------------------------------
stat_ "D3 discovery"
( $PY -m study_b.r3_discover_b2b --comparisons-dir "$R3/comparisons" \
    --output-dir "$R3/discovery" --config "$CFG" --runs 3 ) >> "$LOG" 2>&1 & CHILD=$!; wait $CHILD; CHILD=""
NR=$(ls "$R3"/discovery/run_*/feature_taxonomy.json 2>/dev/null | wc -l | tr -d ' ')
say "D3 done: $NR/3 discovery runs"
[ "$NR" -eq 3 ] || { say "STOP: discovery runs incomplete"; stat_ "stopped: D3 $NR"; exit 4; }

# ---------- D4 union -> screen -> dedup -------------------------------------
stat_ "D4 union/screen/dedup"
if [ ! -s "$R3/taxonomy_union.json" ]; then
  # shape-corrected union (vendored merge expects a flatter run format and
  # silently yields zero features on ours - caught 2026-08-14)
  ( $PY -m study_b.r3_union --input-dir "$R3/discovery" \
      --output "$R3/taxonomy_union.json" ) >> "$LOG" 2>&1 & CHILD=$!; wait $CHILD; CHILD=""
fi
[ -s "$R3/taxonomy_union.json" ] || { say "ABORT: union taxonomy missing"; stat_ "failed: D4 union"; exit 5; }
if [ ! -s "$R3/taxonomy_screened.json" ]; then
  ( $PY -m study_b.answerability_screen --taxonomy "$R3/taxonomy_union.json" \
      --out "$R3/taxonomy_screened.json" ) >> "$LOG" 2>&1 & CHILD=$!; wait $CHILD; CHILD=""
fi
[ -s "$R3/taxonomy_screened.json" ] || { say "ABORT: screen failed"; stat_ "failed: D4 screen"; exit 5; }
say "D4 screen: $(cat "$R3/taxonomy_screened.screen_summary.json" 2>/dev/null)"
if [ ! -s "$R3/dedup/clustered_taxonomy.json" ] && [ ! -d "$R3/dedup" ]; then
  # bfloat16 compat shim around the vendored clustering (transformers 5.x)
  ( $PY -m study_b.r3_dedup --taxonomy "$R3/taxonomy_screened.json" \
      --output-dir "$R3/dedup" --method embedding \
      --sim-threshold 0.85 ) >> "$LOG" 2>&1 & CHILD=$!; wait $CHILD; CHILD=""
fi
say "D4 done (dedup at pre-registered 0.85; silhouette sweep runs at analysis via sweep_threshold)"

# ---------- D5 ablation: template-vs-direct ----------------------------------
stat_ "D5 ablation"
if [ ! -d "$R3/ablation/comparisons" ] || [ "$(ls "$R3"/ablation/comparisons 2>/dev/null | wc -l | tr -d ' ')" -lt 30 ]; then
  ( $PY -c "
import sys
sys.path.insert(0, 'vendor/storyscope')
import importlib
mod = importlib.import_module('storyscope.3_cross_source_comparison.compare_sources')
mod.load_comparison_prompt = lambda: (__import__('pathlib').Path('vendor/storyscope/storyscope/prompts/cross_source_comparison_b2b.md')).read_text(encoding='utf-8')
sys.argv = ['compare_sources', '--templates-dir', '$R3/templates_raw',
            '--output-dir', '$R3/ablation/comparisons', '--config', '$CFG',
            '--parallel', '4', '--batch-size', '3', '--resume']
mod.main()" ) >> "$LOG" 2>&1 & CHILD=$!; wait $CHILD; CHILD=""
fi
( $PY -m study_b.r3_discover_b2b --comparisons-dir "$R3/ablation/comparisons" \
    --output-dir "$R3/ablation/discovery" --config "$CFG" --runs 1 ) >> "$LOG" 2>&1 & CHILD=$!; wait $CHILD; CHILD=""
say "D5 done: ablation discovery complete"

# ---------- snapshot ---------------------------------------------------------
stat_ "R3 snapshot"
tar -czf "outputs/r3-snapshot-$(date +%F).tar.gz" outputs/study_b/r3 2>/dev/null
say "=== R3 DONE - next: R4 style audit, then PI GATE (mini-validation + top-up) before R5 ==="
stat_ "done"
