import json
import os
import sys
from pathlib import Path
from dataclasses import asdict

from service.mlx_ner import Qwen3NerBackend, TYPE_NAMES
from privacyguard.semantic import windows


def main():
    text = json.load(sys.stdin)["text"]
    root = Path(__file__).resolve().parents[1]
    model = Path(os.getenv("PRIVACYGUARD_MODEL_DIR", str(root / "models/qwen3/Qwen3-1.7B-bf16")))
    backend = Qwen3NerBackend(model)
    entities = []
    for offset, chunk in windows(text):
        # Variant B rejects generic legal/business words while retaining
        # named projects and organizations for the ensemble to verify.
        for entity in backend.recognize(chunk, list(TYPE_NAMES), prompt_variant="B"):
            item = asdict(entity)
            item["start"] += offset
            item["end"] += offset
            entities.append(item)
        if not backend.last_response_valid:
            raise RuntimeError("invalid MLX result")
    print(json.dumps(entities, ensure_ascii=False))


if __name__ == "__main__":
    main()
