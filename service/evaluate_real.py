from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from .ner import merge_entities
from .redaction_core import Entity, detect_entities

TYPE_NAMES = {"PERSON": "姓名", "ORGANIZATION": "机构", "PHONE": "电话", "ID_NUMBER": "身份证号", "BANK_CARD": "银行卡号", "ADDRESS": "地址", "CASE_NUMBER": "案号", "CONTRACT_NUMBER": "合同编号", "EMAIL": "邮箱"}


def key(item: Entity | dict) -> tuple[str, str, int, int]:
    if isinstance(item, dict):
        return item["type"], item["value"], int(item["start"]), int(item["end"])
    return item.type, item.value, item.start, item.end


def score(gold: list[dict], pred: list[Entity]) -> dict:
    a, b = {key(item) for item in gold}, {key(item) for item in pred}
    tp, fp, fn = len(a & b), len(b - a), len(a - b)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def validate_gold(record: dict) -> list[str]:
    errors = []
    text = record.get("text", "")
    for i, item in enumerate(record.get("gold_entities", [])):
        try:
            value = text[int(item["start"]):int(item["end"])]
            if value != item["value"]:
                errors.append(f"{record['id']}#{i}:span_mismatch")
            if item["type"] not in TYPE_NAMES:
                errors.append(f"{record['id']}#{i}:unknown_type")
        except (KeyError, TypeError, ValueError):
            errors.append(f"{record['id']}#{i}:invalid_entity")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a human-confirmed local annotation set")
    parser.add_argument("--input", type=Path, help="Human-reviewed JSONL input")
    parser.add_argument("--output", type=Path, help="Evaluation report output")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    # The annotation UI writes the reviewed copy; never score the untouched
    # candidate file, otherwise confirmed labels appear as zero gold entities.
    path = (args.input or root / "test-results/real-annotation-assisted.jsonl").expanduser().resolve()
    out = (args.output or root / "test-results/real-evaluation.json").expanduser().resolve()
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    validation = [error for record in records for error in validate_gold(record)]
    gold_count = sum(len(record.get("gold_entities", [])) for record in records)
    pending_records = [record["id"] for record in records if record.get("review_status") != "confirmed"]
    if validation or pending_records or gold_count == 0:
        report = {"status": "awaiting_human_annotation", "files": len(records), "gold_entities": gold_count, "validation_errors": validation, "pending_records": pending_records, "message": "Confirm every record and ensure every gold span matches the source text before scoring."}
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2
    from .mlx_ner import Qwen3NerBackend, recognize_chunked
    backend = Qwen3NerBackend(root / "models/qwen3/Qwen3-1.7B-bf16")
    totals = defaultdict(lambda: Counter())
    by_type = defaultdict(lambda: defaultdict(Counter))
    for record in records:
        text = record["text"]
        gold = record["gold_entities"]
        requested = list(TYPE_NAMES)
        ner = recognize_chunked(backend, text, requested, prompt_variant="B")
        variants = {"rules": detect_entities(text), "fp16_ner": ner, "hybrid": merge_entities(detect_entities(text), ner)}
        for variant, pred in variants.items():
            result = score(gold, pred)
            totals[variant].update({field: result[field] for field in ("tp", "fp", "fn")})
            for type_id in set(item["type"] for item in gold) | {item.type for item in pred}:
                by_type[variant][type_id].update({field: score([item for item in gold if item["type"] == type_id], [item for item in pred if item.type == type_id])[field] for field in ("tp", "fp", "fn")})
    variants = {name: dict(values) for name, values in totals.items()}
    for result in variants.values():
        tp, fp, fn = result["tp"], result["fp"], result["fn"]
        result["precision"] = tp / (tp + fp) if tp + fp else 1.0
        result["recall"] = tp / (tp + fn) if tp + fn else 1.0
        result["f1"] = 2 * result["precision"] * result["recall"] / (result["precision"] + result["recall"]) if result["precision"] + result["recall"] else 0.0
    report = {"status": "complete", "files": len(records), "gold_entities": gold_count, "sample_size_note": "Small sample; use as an internal directional result, not a production accuracy guarantee.", "variants": variants, "by_type": {name: {type_id: dict(values) for type_id, values in types.items()} for name, types in by_type.items()}}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
