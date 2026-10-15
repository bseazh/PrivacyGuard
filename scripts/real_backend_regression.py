#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import re
import time
import urllib.error
import urllib.request
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "tests/real_samples.json"
DEFAULT_OUTPUT = ROOT / "reports/real-backend-regression"
DEFAULT_LOG = ROOT / "logs/privacyguard.log"


def request_json(url: str, *, payload: dict | None = None, headers: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, headers=headers or {}, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"error": body}


def validate_entities(text: str, entities: list[dict]) -> dict:
    invalid_offsets = []
    duplicates = []
    seen = set()
    overlap_pairs = 0
    ordered = sorted(enumerate(entities), key=lambda item: (item[1].get("start", -1), item[1].get("end", -1)))
    for index, entity in enumerate(entities):
        start, end, value = entity.get("start"), entity.get("end"), entity.get("value")
        if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start or text[start:end] != value:
            invalid_offsets.append(index)
        key = (entity.get("type"), start, end, value)
        if key in seen:
            duplicates.append(index)
        seen.add(key)
    for position, (_, left) in enumerate(ordered):
        for _, right in ordered[position + 1:]:
            if right.get("start", 0) >= left.get("end", 0):
                break
            overlap_pairs += 1
    return {"invalid_offset_indexes": invalid_offsets, "duplicate_indexes": duplicates, "overlap_pairs": overlap_pairs}


def build_preview(text: str, entities: list[dict]) -> tuple[str, int]:
    confirmed = sorted((entity for entity in entities if entity.get("policy") == "must_redact"), key=lambda item: (item["start"], -item["end"]))
    tokens: dict[tuple[str, str], str] = {}
    counters: Counter = Counter()
    output, cursor, count = [], 0, 0
    for entity in confirmed:
        start, end = entity.get("start"), entity.get("end")
        if not isinstance(start, int) or not isinstance(end, int) or start < cursor or text[start:end] != entity.get("value"):
            continue
        identity = (entity["type"], entity["value"])
        if identity not in tokens:
            counters[entity["type"]] += 1
            tokens[identity] = f"<{entity['type']}_{counters[entity['type']]:03d}>"
        output.extend((text[cursor:start], tokens[identity]))
        cursor, count = end, count + 1
    output.append(text[cursor:])
    return "".join(output), count


def run_sample(api: str, sample: dict, output: Path, poll_seconds: float) -> dict:
    path = Path(sample["path"])
    request_id = f"reg-{sample['id']}-{uuid.uuid4().hex[:8]}"
    started = time.perf_counter()
    record = {"id": sample["id"], "name": path.name, "path": str(path), "expect": sample["expect"], "request_id": request_id, "states": []}
    if not path.is_file():
        return record | {"outcome": "failed", "error": "sample file not found"}
    payload = {"name": path.name, "data": base64.b64encode(path.read_bytes()).decode()}
    try:
        status, job = request_json(f"{api}/analyze-upload", payload=payload, headers={"Content-Type": "application/json", "X-Request-ID": request_id})
        if status != 202 or not job.get("job_id"):
            raise RuntimeError(f"job creation failed: HTTP {status} {job}")
        last_state = None
        while True:
            time.sleep(poll_seconds)
            status, state = request_json(f"{api}/jobs/{job['job_id']}")
            if status != 200:
                raise RuntimeError(f"job polling failed: HTTP {status} {state}")
            snapshot = {key: state.get(key) for key in ("status", "phase", "progress", "chunk", "chunks", "message") if key in state}
            if snapshot != last_state:
                snapshot["elapsed_seconds"] = round(time.perf_counter() - started, 3)
                record["states"].append(snapshot)
                last_state = {key: value for key, value in snapshot.items() if key != "elapsed_seconds"}
                print(f"[{sample['id']}] {snapshot}", flush=True)
            if state.get("status") == "done":
                result = state["result"]
                break
            if state.get("status") == "error":
                raise RuntimeError(state.get("message", "unknown backend error"))
        text, entities = result.get("text", ""), result.get("entities", [])
        validation = validate_entities(text, entities)
        preview, token_occurrences = build_preview(text, entities)
        result_path = output / "results" / f"{sample['id']}.json"
        preview_path = output / "previews" / f"{sample['id']}.redacted.txt"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        preview_path.write_text(preview, encoding="utf-8")
        type_counts = Counter(entity.get("type", "UNKNOWN") for entity in entities)
        policy_counts = Counter(entity.get("policy", "unknown") for entity in entities)
        unique_values = len({(entity.get("type"), entity.get("value")) for entity in entities})
        is_no_text = len(text.strip()) < 20
        passed = (sample["expect"] == "no_text" and is_no_text) or (sample["expect"] == "success" and not is_no_text and not validation["invalid_offset_indexes"])
        return record | {
            "outcome": "passed" if passed else "failed",
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "text_chars": len(text), "entity_count": len(entities), "unique_entity_values": unique_values, "token_occurrences": token_occurrences,
            "type_counts": dict(type_counts), "policy_counts": dict(policy_counts), "validation": validation,
            "diagnostics": result.get("diagnostics", {}),
            "result_file": str(result_path), "preview_file": str(preview_path)
        }
    except Exception as exc:
        return record | {"outcome": "failed", "elapsed_seconds": round(time.perf_counter() - started, 3), "error": f"{type(exc).__name__}: {exc}"}


def write_summary(output: Path, records: list[dict], started_at: str) -> None:
    payload = {"started_at": started_at, "finished_at": datetime.now().astimezone().isoformat(), "technical_passed": sum(item["outcome"] == "passed" for item in records), "technical_failed": sum(item["outcome"] != "passed" for item in records), "quality_warnings": sum(bool(item.get("quality_warning")) for item in records), "samples": records}
    (output / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Real Backend Regression", "", f"Started: `{started_at}`", f"Finished: `{payload['finished_at']}`", "", f"Technical result: **{payload['technical_passed']} passed, {payload['technical_failed']} failed**", f"Quality result: **{payload['quality_warnings']} samples require review**", "", "| ID | Format | Expected | Technical | Quality | Chars | Entities | Seconds | Offset errors |", "|---|---|---|---:|---|---:|---:|---:|---:|"]
    for item in records:
        quality = item.get("quality_warning") or "ok"
        lines.append(f"| {item['id']} | {Path(item['name']).suffix.lower()} | {item['expect']} | {item['outcome']} | {quality} | {item.get('text_chars', '-')} | {item.get('entity_count', '-')} | {item.get('elapsed_seconds', '-')} | {len(item.get('validation', {}).get('invalid_offset_indexes', []))} |")
    lines.extend(["", "## Notes", "", "- All processing used the local API and local Qwen3 model.", "- Raw extracted text and entity output remain under the local `results/` directory.", "- Preview files auto-confirm only `must_redact` candidates for deterministic regression; production export still requires human review.", "- A scanned PDF with fewer than 20 non-whitespace characters is treated as the expected no-text boundary."])
    (output / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def attach_backend_logs(output: Path, records: list[dict], log_path: Path) -> None:
    if not log_path.is_file():
        return
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    log_dir = output / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    for record in records:
        matched = [line for line in lines if f"id={record['request_id']}" in line]
        (log_dir / f"{record['id']}.log").write_text("\n".join(matched) + ("\n" if matched else ""), encoding="utf-8")
        chunk_times = []
        for line in matched:
            found = re.search(r"ner_chunk_done .* chunk=(\d+) chunks=(\d+) .* elapsed_ms=(\d+)", line)
            if found:
                chunk_times.append({"chunk": int(found.group(1)), "chunks": int(found.group(2)), "elapsed_ms": int(found.group(3))})
        record["chunk_timings"] = chunk_times
        record["backend_log_file"] = str(log_dir / f"{record['id']}.log")
        if record.get("expect") == "success":
            chars, count = record.get("text_chars", 0), record.get("entity_count", 0)
            if count == 0:
                record["quality_warning"] = "zero entities"
            elif chars >= 5000 and count * 1000 / chars < 0.5:
                record["quality_warning"] = "very low entity density"
            if record.get("diagnostics", {}).get("parse_failures"):
                record["quality_warning"] = "unrecovered NER parse failures"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8766")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--poll-seconds", type=float, default=0.7)
    parser.add_argument("--only", action="append", help="Run one sample ID; may be repeated")
    parser.add_argument("--resume", action="store_true", help="Keep completed samples in an existing output directory")
    parser.add_argument("--report-only", action="store_true", help="Rebuild report and attach logs without inference")
    args = parser.parse_args()
    if args.report_only:
        existing = json.loads((args.output / "summary.json").read_text(encoding="utf-8"))
        records = existing["samples"]
        attach_backend_logs(args.output, records, DEFAULT_LOG)
        write_summary(args.output, records, existing["started_at"])
        return 0
    status, health = request_json(f"{args.api}/health")
    if status != 200 or not health.get("ok"):
        raise SystemExit(f"Local API is unavailable: HTTP {status} {health}")
    samples = json.loads(args.manifest.read_text(encoding="utf-8"))
    if args.only:
        samples = [sample for sample in samples if sample["id"] in set(args.only)]
    args.output.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now().astimezone().isoformat()
    records = []
    if args.resume and (args.output / "summary.json").is_file():
        existing = json.loads((args.output / "summary.json").read_text(encoding="utf-8"))
        started_at = existing["started_at"]
        records = existing["samples"]
        completed = {item["id"] for item in records}
        samples = [sample for sample in samples if sample["id"] not in completed]
    for sample in samples:
        record = run_sample(args.api, sample, args.output, args.poll_seconds)
        records.append(record)
        write_summary(args.output, records, started_at)
        print(f"[{sample['id']}] outcome={record['outcome']} elapsed={record.get('elapsed_seconds')}s", flush=True)
    attach_backend_logs(args.output, records, DEFAULT_LOG)
    write_summary(args.output, records, started_at)
    return 1 if any(item["outcome"] != "passed" for item in records) else 0


if __name__ == "__main__":
    raise SystemExit(main())
