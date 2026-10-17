from __future__ import annotations

import argparse
import json
from pathlib import Path

from .mlx_ner import Qwen3NerBackend, TYPE_NAMES, recognize_chunked
from .redaction_core import detect_entities, extract_text


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare local annotation candidates without committing source paths or documents")
    parser.add_argument("sources", nargs="+", type=Path, help="Local documents to process; never written into repository configuration")
    parser.add_argument("--output", type=Path, help="Local JSONL output (defaults to test-results/real-annotation-candidates.jsonl)")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    backend = Qwen3NerBackend(root / "models/qwen3/Qwen3-1.7B-bf16")
    requested = list(TYPE_NAMES)
    output = (args.output or root / "test-results/real-annotation-candidates.jsonl").expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for index, source in enumerate(args.sources, 1):
            text = extract_text(source)
            # Keep model context bounded and preserve global offsets.
            candidates = []
            for entity in recognize_chunked(backend, text, requested, chunk_chars=2400, overlap=300, prompt_variant="B"):
                candidates.append({"type": entity.type, "value": entity.value, "start": entity.start, "end": entity.end, "source": "fp16_ner", "review": "pending"})
            rules = [item.__dict__ | {"review": "pending"} for item in detect_entities(text)]
            record = {
                "id": f"real-{index:02d}",
                "source_path": str(source),
                "format": source.suffix.lower().lstrip("."),
                "text": text,
                "candidates": candidates,
                "rule_candidates": rules,
                "gold_entities": [],
                "review_notes": "",
                "review_status": "pending",
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(record["id"], len(text), len(candidates), len(rules))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
