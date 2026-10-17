from __future__ import annotations

import argparse
import json
from pathlib import Path


def key(item: dict) -> tuple[str, str, int, int]:
    return item["type"], item["value"], int(item["start"]), int(item["end"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge local rule and MLX candidates for human review")
    parser.add_argument("--input", type=Path, help="Candidate JSONL input")
    parser.add_argument("--output", type=Path, help="Assisted JSONL output")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = (args.input or root / "test-results/real-annotation-candidates.jsonl").expanduser().resolve()
    target = (args.output or root / "test-results/real-annotation-assisted.jsonl").expanduser().resolve()
    records = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    for record in records:
        rules = {key(item): item for item in record.get("rule_candidates", [])}
        ner = {key(item): item for item in record.get("candidates", [])}
        all_keys = sorted(set(rules) | set(ner), key=lambda item: (item[2], item[3], item[0]))
        assisted = []
        for entity_key in all_keys:
            item = rules.get(entity_key) or ner.get(entity_key)
            sources = []
            if entity_key in rules: sources.append("rules")
            if entity_key in ner: sources.append("fp16_ner")
            confidence = "high_candidate" if len(sources) == 2 else "needs_review"
            assisted.append({**{field: item[field] for field in ("type", "value", "start", "end")}, "sources": sources, "ai_status": confidence, "human_status": "pending"})
        record["assisted_candidates"] = assisted
        record["gold_entities"] = []
        record["review_status"] = "pending"
        record["review_notes"] = "AI-assisted candidates are not gold labels. Confirm, edit, or reject each candidate. Add missed entities manually."
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    summary = {"files": len(records), "candidates": sum(len(item["assisted_candidates"]) for item in records), "high_candidates": sum(sum(x["ai_status"] == "high_candidate" for x in item["assisted_candidates"]) for item in records), "needs_review": sum(sum(x["ai_status"] == "needs_review" for x in item["assisted_candidates"]) for item in records)}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
