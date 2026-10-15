from __future__ import annotations

import json
import base64
import logging
import time
import tempfile
import threading
import traceback
import uuid
import os
import hashlib
from logging.handlers import RotatingFileHandler
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .ner import merge_entities
from .pdf_redactor import PdfRedactionError, redact_pdf_bytes
from .redaction_core import Entity, detect_entities, extract_text, tokenize

try:
    from .mlx_ner import Qwen3NerBackend, TYPE_NAMES
    MLX_IMPORT_ERROR = None
except ImportError as exc:
    Qwen3NerBackend = None
    MLX_IMPORT_ERROR = exc
    TYPE_NAMES = {
        "PERSON": "姓名", "ORGANIZATION": "机构", "ADDRESS": "地址", "DEPARTMENT": "部门", "PROJECT": "项目名",
        "COURT": "法院", "LAW_FIRM": "律师事务所", "PLAINTIFF": "原告", "DEFENDANT": "被告",
        "APPLICANT": "申请人", "RESPONDENT": "被申请人", "ATTORNEY": "代理人", "LEGAL_REPRESENTATIVE": "法定代表人",
    }

ROOT = Path(os.environ.get("PRIVACYGUARD_ROOT", os.environ.get("LEGALREDACTION_ROOT", Path(__file__).resolve().parents[1]))).resolve()
HOST, PORT = "127.0.0.1", 8766
MODEL = Path(os.environ.get("PRIVACYGUARD_MODEL_DIR", os.environ.get("LEGALREDACTION_MODEL_DIR", ROOT / "models/qwen3/Qwen3-1.7B-bf16"))).resolve()
NER_MODE = os.environ.get("PRIVACYGUARD_NER_BACKEND", "auto").strip().lower()
LOG_DIR = Path(os.environ.get("PRIVACYGUARD_LOG_DIR", os.environ.get("LEGALREDACTION_LOG_DIR", ROOT / "logs"))).resolve()
LOG_FILE = LOG_DIR / "privacyguard.log"
LOG_DIR.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger("privacyguard.api")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = RotatingFileHandler(LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
_backend = None
_lock = threading.Lock()
_inference_lock = threading.Lock()
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()
NER_CHUNK_CHARS = 6000
NER_CHUNK_OVERLAP = 300
POLICY = {
    "PERSON": "must_redact", "PHONE": "must_redact", "ID_NUMBER": "must_redact", "BANK_CARD": "must_redact", "ADDRESS": "must_redact", "EMAIL": "must_redact",
    "ORGANIZATION": "manual_review", "DEPARTMENT": "manual_review", "PROJECT": "manual_review", "COURT": "manual_review", "LAW_FIRM": "manual_review",
    "PLAINTIFF": "must_redact", "DEFENDANT": "must_redact", "APPLICANT": "must_redact", "RESPONDENT": "must_redact", "ATTORNEY": "must_redact", "LEGAL_REPRESENTATIVE": "must_redact",
    "CASE_NUMBER": "do_not_redact", "CONTRACT_NUMBER": "do_not_redact",
}


def recognize_with_fallback(text: str, entity_types: list[str], depth: int = 0) -> tuple[list[Entity], int, int]:
    engine = backend()
    entities = engine.recognize(text, entity_types, prompt_variant="B")
    if engine.last_response_valid:
        return entities, 0, 0
    if len(text) <= 1200 or depth >= 2:
        logger.error("ner_response_abandoned depth=%d chars=%d error=%s", depth, len(text), engine.last_response_error)
        return [], 0, 1
    cut = len(text) // 2
    overlap = min(150, max(0, cut // 4))
    right_start = max(0, cut - overlap)
    logger.warning("ner_response_retry_split depth=%d chars=%d left_chars=%d right_chars=%d", depth, len(text), cut + overlap, len(text) - right_start)
    left, left_retries, left_failures = recognize_with_fallback(text[:cut + overlap], entity_types, depth + 1)
    right, right_retries, right_failures = recognize_with_fallback(text[right_start:], entity_types, depth + 1)
    shifted = [Entity(item.type, item.value, right_start + item.start, right_start + item.end, item.confidence, item.source) for item in right]
    return left + shifted, 1 + left_retries + right_retries, left_failures + right_failures


def backend() -> Qwen3NerBackend:
    global _backend
    with _lock:
        if _backend is None:
            if Qwen3NerBackend is None:
                raise RuntimeError(
                    "MLX 语义模型不可用。Windows/Intel Mac 请设置 PRIVACYGUARD_NER_BACKEND=rules 使用规则模式；"
                    f"原始错误：{MLX_IMPORT_ERROR}"
                )
            logger.info("model_load_start path=%s", MODEL)
            _backend = Qwen3NerBackend(MODEL)
            logger.info("model_load_done")
        return _backend


def analyze(path: Path, job_id: str | None = None, display_name: str | None = None) -> dict:
    started = time.perf_counter()
    log_name = "file-" + hashlib.sha256((display_name or path.name).encode()).hexdigest()[:12]
    logger.info("analyze_start id=%s name=%s suffix=%s size=%d", job_id or "direct", log_name, path.suffix.lower(), path.stat().st_size)
    text = extract_text(path)
    logger.info("extract_done id=%s name=%s chars=%d elapsed_ms=%d", job_id or "direct", log_name, len(text), round((time.perf_counter() - started) * 1000))
    rules = detect_entities(text)
    logger.info("rules_done id=%s name=%s entities=%d", job_id or "direct", log_name, len(rules))
    queue_started = time.perf_counter()
    logger.info("ner_queue_wait id=%s name=%s", job_id or "direct", log_name)
    with _inference_lock:
        logger.info("ner_queue_acquired id=%s name=%s wait_ms=%d", job_id or "direct", log_name, round((time.perf_counter() - queue_started) * 1000))
        ner = []
        step = NER_CHUNK_CHARS - NER_CHUNK_OVERLAP
        chunks = max(1, (max(0, len(text) - NER_CHUNK_OVERLAP) + step - 1) // step)
        logger.info("ner_chunks_start id=%s name=%s chunks=%d chunk_chars=%d", job_id or "direct", log_name, chunks, NER_CHUNK_CHARS)
        seen = set()
        parse_retries = 0
        parse_failures = 0
        offsets = [] if NER_MODE == "rules" else range(0, len(text), step)
        for chunk_index, offset in enumerate(offsets, start=1):
            chunk = text[offset : offset + NER_CHUNK_CHARS]
            if not chunk.strip():
                continue
            if job_id:
                with _jobs_lock:
                    _jobs[job_id].update({"status": "running", "phase": "ner", "chunk": chunk_index, "chunks": chunks, "progress": min(95, 30 + round(chunk_index * 65 / chunks)), "message": f"模型识别中：第 {chunk_index} / {chunks} 段"})
            logger.info("ner_chunk_start id=%s name=%s chunk=%d chunks=%d offset=%d chars=%d", job_id or "direct", log_name, chunk_index, chunks, offset, len(chunk))
            chunk_started = time.perf_counter()
            chunk_entities, chunk_retries, chunk_failures = recognize_with_fallback(chunk, list(TYPE_NAMES))
            parse_retries += chunk_retries
            parse_failures += chunk_failures
            for entity in chunk_entities:
                start, end = offset + entity.start, offset + entity.end
                key = (entity.type, start, end, entity.value)
                if key not in seen:
                    seen.add(key)
                    ner.append(Entity(entity.type, entity.value, start, end, entity.confidence, entity.source))
            logger.info("ner_chunk_done id=%s name=%s chunk=%d chunks=%d total_entities=%d retries=%d failures=%d elapsed_ms=%d", job_id or "direct", log_name, chunk_index, chunks, len(ner), chunk_retries, chunk_failures, round((time.perf_counter() - chunk_started) * 1000))
            if offset + NER_CHUNK_CHARS >= len(text):
                break
        logger.info("ner_chunks_done id=%s name=%s chunks=%d unique_entities=%d mode=%s", job_id or "direct", log_name, chunks, len(ner), NER_MODE)
    logger.info("ner_done id=%s name=%s entities=%d elapsed_ms=%d", job_id or "direct", log_name, len(ner), round((time.perf_counter() - started) * 1000))
    entities = merge_entities(rules, ner)
    logger.info("analyze_done id=%s name=%s rules=%d ner=%d entities=%d elapsed_ms=%d", job_id or "direct", log_name, len(rules), len(ner), len(entities), round((time.perf_counter() - started) * 1000))
    payload_entities = []
    review_counts = {"automatic": 0, "review": 0, "ignored_by_default": 0}
    for entity in entities:
        policy = POLICY.get(entity.type, "manual_review")
        review = "confirmed" if policy == "must_redact" else "pending"
        if policy == "must_redact": review_counts["automatic"] += 1
        elif policy == "manual_review": review_counts["review"] += 1
        else: review_counts["ignored_by_default"] += 1
        payload_entities.append(entity.__dict__ | {"policy": policy, "review": review})
    review_status = "REVIEW" if review_counts["review"] else "READY"
    return {"path": str(path), "name": path.name, "text": text, "entities": payload_entities,
            "review_status": review_status, "review_counts": review_counts,
            "supported_types": list(TYPE_NAMES), "policy": POLICY,
            "diagnostics": {"parse_retries": parse_retries, "parse_failures": parse_failures, "chunks": chunks, "ner_mode": NER_MODE}}


def run_job(job_id: str, name: str, raw: bytes, suffix: str) -> None:
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(prefix="privacyguard-", suffix=suffix, delete=False) as temporary:
            temporary.write(raw); temp_path = Path(temporary.name)
        with _jobs_lock:
            _jobs[job_id].update({"phase": "extract", "message": "正在提取文本"})
        log_name = "file-" + hashlib.sha256(name.encode()).hexdigest()[:12]
        logger.info("job_start id=%s name=%s suffix=%s size=%d", job_id, log_name, suffix, len(raw))
        result = analyze(temp_path, job_id, name)
        result["name"] = name; result["path"] = "local-upload"
        with _jobs_lock:
            _jobs[job_id].update({"status": "done", "phase": "done", "progress": 100, "message": f"识别完成：{len(result['entities'])} 个候选", "result": result})
        logger.info("job_done id=%s name=%s entities=%d", job_id, log_name, len(result["entities"]))
    except Exception as exc:
        log_name = "file-" + hashlib.sha256(name.encode()).hexdigest()[:12]
        logger.error("job_error id=%s name=%s type=%s", job_id, log_name, type(exc).__name__)
        with _jobs_lock:
            _jobs[job_id].update({"status": "error", "phase": "error", "message": str(exc)})
    finally:
        if temp_path: temp_path.unlink(missing_ok=True)


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status: int, payload: object) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Access-Control-Allow-Origin", "*"); self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS"); self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Request-ID"); self.send_header("Access-Control-Allow-Private-Network", "true"); self.send_header("X-Request-ID", getattr(self, "_request_id", "")); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def do_OPTIONS(self) -> None:
        logger.info("cors_preflight path=%s origin=%s requested_headers=%s private_network=%s", self.path, self.headers.get("Origin", ""), self.headers.get("Access-Control-Request-Headers", ""), self.headers.get("Access-Control-Request-Private-Network", ""))
        self.send_response(204); self.send_header("Access-Control-Allow-Origin", "*"); self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS"); self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Request-ID"); self.send_header("Access-Control-Allow-Private-Network", "true"); self.send_header("Access-Control-Max-Age", "600"); self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/health": self.send_json(200, {"ok": True, "runtime": "rules" if NER_MODE == "rules" else "MLX", "model": str(MODEL), "pdf_redaction": True}); return
        if self.path.startswith("/jobs/"):
            job_id = self.path.split("/", 2)[-1]
            with _jobs_lock:
                job = dict(_jobs.get(job_id, {"status": "missing", "message": "job not found"}))
            self.send_json(200 if job.get("status") != "missing" else 404, job); return
        self.send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path not in {"/analyze", "/analyze-upload", "/redact-pdf-upload"}: self.send_json(404, {"error": "not found"}); return
        request_id = self.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        self._request_id = request_id
        started = time.perf_counter()
        logger.info("request_start id=%s method=POST path=%s content_length=%s", request_id, self.path, self.headers.get("Content-Length", "0"))
        try:
            length = int(self.headers.get("Content-Length", "0")); payload = json.loads(self.rfile.read(length))
            if self.path == "/redact-pdf-upload":
                name = Path(str(payload.get("name", "document.pdf"))).name
                if Path(name).suffix.lower() != ".pdf": raise ValueError("PDF redaction requires a .pdf file")
                raw = base64.b64decode(str(payload["data"]), validate=True)
                entities = payload.get("entities", [])
                if not isinstance(entities, list): raise ValueError("entities must be an array")
                mode = str(payload.get("replacement_mode", "semantic"))
                redacted, audit = redact_pdf_bytes(raw, entities, mode)
                output_name = f"{Path(name).stem}.pseudonymized.pdf"
                self.send_json(200, {"name": output_name, "data": base64.b64encode(redacted).decode(), "audit": audit})
            elif self.path == "/analyze-upload":
                name = Path(str(payload.get("name", "upload.txt"))).name
                suffix = Path(name).suffix.lower()
                if suffix not in {".txt", ".md", ".eml", ".docx", ".pdf"}: raise ValueError("unsupported file type")
                raw = base64.b64decode(str(payload["data"]), validate=True)
                job_id = request_id
                logger.info("job_created id=%s name=%s suffix=%s size=%d", job_id, name, suffix, len(raw))
                with _jobs_lock:
                    _jobs[job_id] = {"status": "queued", "phase": "queued", "progress": 0, "name": name, "message": "已排队"}
                threading.Thread(target=run_job, args=(job_id, name, raw, suffix), daemon=True).start()
                self.send_json(202, {"job_id": job_id, "status": "queued", "name": name, "message": "任务已创建"})
            else:
                path = Path(str(payload["path"])).expanduser().resolve()
                if not path.is_file(): raise ValueError("file not found")
                self.send_json(200, analyze(path))
        except BrokenPipeError:
            logger.warning("request_client_disconnected id=%s", request_id)
        except (PdfRedactionError, ValueError) as exc:
            logger.warning("request_rejected id=%s type=%s error=%s", request_id, type(exc).__name__, exc)
            self.send_json(400, {"error": str(exc)})
        except Exception as exc:
            logger.error("request_error id=%s type=%s error=%s\n%s", request_id, type(exc).__name__, exc, traceback.format_exc())
            self.send_json(400, {"error": str(exc)})
        finally:
            logger.info("request_done id=%s elapsed_ms=%d", request_id, round((time.perf_counter() - started) * 1000))

    def log_message(self, *_args) -> None: return


def main() -> None:
    logger.info("service_start host=%s port=%d model=%s log_file=%s", HOST, PORT, MODEL, LOG_FILE)
    print(f"PrivacyGuard local API: http://{HOST}:{PORT} (log: {LOG_FILE})")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__": main()
