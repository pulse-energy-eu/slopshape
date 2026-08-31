#!/usr/bin/env python
"""Dedup driver: vendored clustering with a bfloat16 compat shim.

transformers 5.x loads F2LLM-4B in bfloat16, which numpy cannot convert
("TypeError: Got unsupported ScalarType BFloat16"), so the vendored
compute_embeddings dies at .cpu().numpy(). This driver reimplements that one
function with an added .float() cast - pooling, batching, truncation and the
model identity are otherwise IDENTICAL to the vendored code - then delegates
to the vendored main() so clustering, threshold handling and condensation stay
exactly the paper's.

  .venv/bin/python -m study_b.r3_dedup --taxonomy outputs/study_b/r3/taxonomy_screened.json \
      --output-dir outputs/study_b/r3/dedup --sim-threshold 0.85
"""
import importlib
import sys
from pathlib import Path
from typing import List

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "vendor/storyscope"))

cf_mod = importlib.import_module("storyscope.4_feature_discovery.cluster_features")


def compute_embeddings_f32(features: List[dict], model_name: str,
                           batch_size: int = 8, device: str = "auto") -> np.ndarray:
    """Vendored compute_embeddings + .float() before numpy conversion."""
    import torch
    from transformers import AutoTokenizer, AutoModel

    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"

    cf_mod.logger.info(f"Loading embedding model: {model_name} on {device} (f32 shim)")
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModel.from_pretrained(model_name, trust_remote_code=True).to(device)
    model.eval()

    texts = [cf_mod.feature_to_text(f) for f in features]
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        inputs = tokenizer(batch, padding=True, truncation=True, max_length=512,
                           return_tensors="pt").to(device)
        with torch.no_grad():
            outputs = model(**inputs)
            if hasattr(outputs, "pooler_output") and outputs.pooler_output is not None:
                embeddings = outputs.pooler_output
            else:
                embeddings = outputs.last_hidden_state.mean(dim=1)
        all_embeddings.append(embeddings.float().cpu().numpy())
        if (i // batch_size) % 5 == 0:
            cf_mod.logger.info(f"  embedded {min(i + batch_size, len(texts))}/{len(texts)}")

    return np.concatenate(all_embeddings, axis=0)


def main() -> int:
    cf_mod.compute_embeddings = compute_embeddings_f32
    cf_mod.main()
    return 0


if __name__ == "__main__":
    sys.argv[0] = "cluster_features"
    sys.exit(main())
