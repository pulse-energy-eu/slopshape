#!/usr/bin/env python
"""Battery items 8.11 + 8.12: template-vs-direct ablation analysis and the
dedup silhouette threshold sweep. Label-blind throughout; no LLM spend.

  .venv/bin/python -m study_b.r6_writeups
"""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

R3 = Path("outputs/study_b/r3")
OUT = Path("outputs/study_b/r6/results")


def load_run_features(tax_path: Path) -> list[dict]:
    tax = json.loads(tax_path.read_text())
    feats = []
    for dim, dbody in tax.items():
        if not isinstance(dbody, dict):
            continue
        inner = dbody.get("feature_taxonomy", dbody)
        for k, v in (inner.items() if "aspects" not in dbody else [(dim, dbody)]):
            if isinstance(v, dict) and "aspects" in v:
                for abody in v["aspects"].values():
                    for f in abody.get("features") or []:
                        if isinstance(f, dict) and f.get("id"):
                            feats.append({**f, "dim": dim})
    return feats


def embed(texts: list[str]) -> np.ndarray:
    import torch
    from transformers import AutoTokenizer, AutoModel
    name = "codefuse-ai/F2LLM-4B"
    tok = AutoTokenizer.from_pretrained(name, trust_remote_code=True)
    model = AutoModel.from_pretrained(name, trust_remote_code=True)
    model.eval()
    outs = []
    for i in range(0, len(texts), 8):
        batch = tok(texts[i:i + 8], padding=True, truncation=True,
                    max_length=256, return_tensors="pt")
        with torch.no_grad():
            o = model(**batch)
            e = (o.pooler_output if getattr(o, "pooler_output", None) is not None
                 else o.last_hidden_state.mean(dim=1))
        outs.append(e.float().numpy())
        if (i // 8) % 10 == 0:
            print(f"  embed {i}/{len(texts)}", flush=True)
    E = np.concatenate(outs)
    return E / np.linalg.norm(E, axis=1, keepdims=True)


def ftext(f):
    vals = ", ".join(str(v) for v in f.get("values", []))
    return f"{f.get('name', f['id'])}: {f.get('question','')}  Values: {vals}"


def main() -> int:
    # ---------------- 8.11 template-vs-direct --------------------------------
    union = load_run_features(R3 / "taxonomy_union.json")
    abl = load_run_features(R3 / "ablation" / "discovery" / "run_1" / "feature_taxonomy.json")
    tpl_run1 = load_run_features(R3 / "discovery" / "run_1" / "feature_taxonomy.json")
    dims_u = Counter(f["dim"] for f in union)
    dims_a = Counter(f["dim"] for f in abl)
    print(f"union {len(union)} | template run1 {len(tpl_run1)} | ablation raw run {len(abl)}", flush=True)

    print("embedding union + ablation features...", flush=True)
    Eu = embed([ftext(f) for f in union])
    Ea = embed([ftext(f) for f in abl])
    sim = Ea @ Eu.T
    cov_a_in_u = float((sim.max(axis=1) >= 0.85).mean())   # ablation features covered by template set
    cov_u_in_a = float((sim.T.max(axis=1) >= 0.85).mean()) # template features covered by raw set
    def optstats(fs):
        n = [len(f.get("values", [])) for f in fs]
        return {"mean_options": round(float(np.mean(n)), 2),
                "share_ge2_options": round(float(np.mean([x >= 2 for x in n])), 3)}
    r811 = {
        "template_runs_features": {"run1": len(tpl_run1), "union_3runs": len(union)},
        "raw_text_run_features": len(abl),
        "dimension_coverage": {"template_union_dims": len(dims_u), "raw_dims": len(dims_a),
                                "raw_missing_dims": sorted(set(dims_u) - set(dims_a))},
        "semantic_overlap_at_0.85": {
            "raw_features_covered_by_template_set": round(cov_a_in_u, 3),
            "template_features_covered_by_raw_set": round(cov_u_in_a, 3)},
        "option_structure": {"template_union": optstats(union), "raw": optstats(abl)},
    }
    print("8.11:", json.dumps(r811), flush=True)

    # ---------------- 8.12 dedup silhouette sweep ----------------------------
    import importlib
    sys.path.insert(0, "vendor/storyscope")
    cf = importlib.import_module("storyscope.4_feature_discovery.cluster_features")
    from sklearn.metrics import silhouette_score
    E282 = np.load(R3 / "dedup" / "feature_embeddings.npy")
    E282 = E282 / np.linalg.norm(E282, axis=1, keepdims=True)
    sweep = []
    for t in (0.70, 0.75, 0.80, 0.85, 0.90, 0.95):
        clusters = cf.cluster_by_cosine(E282, t)
        labels = np.empty(len(E282), dtype=int)
        for ci, idxs in enumerate(clusters):
            for i in idxs:
                labels[i] = ci
        n_clusters = len(clusters)
        n_merged = len(E282) - n_clusters
        if 1 < n_clusters < len(E282):
            sil = round(float(silhouette_score(E282, labels, metric="cosine")), 4)
        else:
            sil = None
        sweep.append({"threshold": t, "features_after": n_clusters,
                      "merged": n_merged, "silhouette": sil})
        print(f"  t={t}: {n_clusters} features, sil={sil}", flush=True)
    r812 = {"method": "single-linkage cosine over F2LLM-4B embeddings of the 282 "
                       "screened features (label-blind)",
            "preregistered_threshold": 0.85, "sweep": sweep}

    json.dump({"t811_template_vs_direct": r811, "t812_dedup_sweep": r812},
              open(OUT / "writeups_811_812.json", "w"), indent=2)
    print("WRITEUPS DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
