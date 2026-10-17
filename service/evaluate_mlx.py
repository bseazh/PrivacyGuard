from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .mlx_ner import Qwen3NerBackend, recognize_chunked
from .ner import merge_entities
from .redaction_core import Entity, detect_entities


def key(item: Entity | dict) -> tuple[str, str, int, int]:
    if isinstance(item, dict):
        return item["type"], item["value"], int(item["start"]), int(item["end"])
    return item.type, item.value, item.start, item.end


def metrics(gold: list[dict], prediction: list[Entity]) -> dict:
    expected = {key(item) for item in gold}
    actual = {key(item) for item in prediction}
    tp, fp, fn = len(expected & actual), len(actual - expected), len(expected - actual)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    samples = [json.loads(line) for line in (root / "test-data/ner-gold.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    backend = Qwen3NerBackend(root / "models/qwen3/Qwen3-1.7B-bf16")
    totals = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    details = []
    for sample in samples:
        text = sample["text"]
        types = sorted({item["type"] for item in sample["entities"]})
        rules = detect_entities(text)
        ner = recognize_chunked(backend, text, types, prompt_variant="B")
        variants = {"rules": rules, "fp16_ner": ner, "hybrid": merge_entities(rules, ner)}
        row = {"id": sample["id"], "counts": {}}
        for name, entities in variants.items():
            result = metrics(sample["entities"], entities)
            row["counts"][name] = result
            for field in ("tp", "fp", "fn"):
                totals[name][field] += result[field]
        details.append(row)
    for result in totals.values():
        tp, fp, fn = result["tp"], result["fp"], result["fn"]
        result["precision"] = tp / (tp + fp) if tp + fp else 1.0
        result["recall"] = tp / (tp + fn) if tp + fn else 1.0
        result["f1"] = 2 * result["precision"] * result["recall"] / (result["precision"] + result["recall"]) if result["precision"] + result["recall"] else 0.0
    report = {"model": str(root / "models/qwen3/Qwen3-1.7B-bf16"), "variants": dict(totals), "samples": details, "note": "Synthetic gold corpus only; all NER values are offset-validated before scoring."}
    output = root / "test-results/ner-m2-fp16-comparison.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
