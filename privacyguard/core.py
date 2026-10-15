from __future__ import annotations

import hashlib
import re
import secrets
from pathlib import Path

from .adapters.presidio import PresidioAdapter
from .adapters.redaction_everything import RedactionEverythingAdapter
from .config import Settings
from .models import Finding
from .semantic import SemanticEnsemble, windows, verified_findings
from .safe_files import inspect_source, rebuild_safe_file, verify_output
from .rules import counts, detect_with_rules, merge_findings, replace_with_tokens
from .security import validate_source_path
from .store import ReferenceError, SafeReferenceStore


UNCERTAIN_SEMANTIC_TYPES = {"PROJECT", "ORGANIZATION", "ADDRESS", "DEPARTMENT", "COURT", "LAW_FIRM"}
SEMANTIC_EXPORT_THRESHOLD = 0.85


class ReviewRequiredError(ValueError):
    pass


class PrivacyGuard:
    def __init__(self, settings: Settings | None = None, presidio: PresidioAdapter | None = None):
        self.settings = settings or Settings.from_env()
        self.presidio = presidio or PresidioAdapter(self.settings.presidio_url)
        self.redaction = RedactionEverythingAdapter(self.settings.redaction_url, self.settings.redaction_token)
        self.store = SafeReferenceStore(self.settings.data_dir, self.settings.reference_ttl_seconds)
        self.semantic = SemanticEnsemble(self.redaction)

    def detect(self, text: str, semantic: bool = True, approved_tokens: bool = False) -> list[Finding]:
        if approved_tokens:
            # Exclude only our generated placeholders from re-detection, preserving offsets.
            text = re.sub(r"<[A-Z_]+_[0-9]{3,}>", lambda match: " " * len(match.group()), text)
        findings = self.semantic.analyze(text) if semantic else []
        findings.extend(detect_with_rules(text))
        for offset, chunk in windows(text):
            for item in self.presidio.analyze(chunk):
                if not 0 <= item.start < item.end <= len(chunk):
                    raise ValueError("Presidio 实体区间无效")
                findings.append(Finding(item.entity_type, offset + item.start, offset + item.end, item.score, item.source))
        for item in list(findings):
            if not 0 <= item.start < item.end <= len(text):
                raise ValueError("实体区间无效")
            value = text[item.start:item.end]
            if len(value.strip()) < 2:
                continue
            for match in re.finditer(re.escape(value), text):
                findings.append(Finding(item.entity_type, match.start(), match.end(), item.score, "repeat-expansion"))
        return merge_findings(findings)

    def _protect(self, text: str, extra: list[Finding], semantic: bool) -> tuple[list[Finding], str]:
        findings = merge_findings(self.detect(text, semantic), extra)
        for _ in range(3):
            if any(not 0 <= item.start < item.end <= len(text) for item in findings):
                raise ValueError("实体区间无效")
            safe_text = replace_with_tokens(text, findings)
            residual = self.detect(safe_text, semantic, approved_tokens=True)
            if not residual:
                return findings, safe_text
            # Map recheck offsets back to the original, never lose earlier redactions.
            segments = []
            original_cursor = safe_cursor = 0
            for item in findings:
                length = item.start - original_cursor
                segments.append((safe_cursor, safe_cursor + length, original_cursor, item.start, False))
                safe_cursor += length
                token = re.match(r"<[A-Z_]+_[0-9]{3,}>", safe_text[safe_cursor:])
                if token is None:
                    raise ValueError("替换区间无法验证")
                length = len(token.group())
                segments.append((safe_cursor, safe_cursor + length, item.start, item.end, True))
                safe_cursor += length
                original_cursor = item.end
            segments.append((safe_cursor, len(safe_text), original_cursor, len(text), False))
            additions = []
            for item in residual:
                ranges = []
                for start, end, raw_start, raw_end, token in segments:
                    left, right = max(start, item.start), min(end, item.end)
                    if left < right:
                        ranges.append((raw_start, raw_end) if token else (raw_start + left - start, raw_start + right - start))
                if not ranges:
                    raise ValueError("复检区间无法验证")
                additions.append(Finding(item.entity_type, min(x[0] for x in ranges), max(x[1] for x in ranges), item.score, "recheck"))
            findings = merge_findings(findings, additions)
        raise ValueError("多轮二次检测仍发现敏感信息")

    @staticmethod
    def _blocked(reason: str) -> dict:
        return {"status": "blocked", "reason": reason, "counts": {}, "safe_reference": None}

    def scrub_text(self, text: str, extra_findings: list[Finding] | None = None, semantic: bool = True) -> dict:
        if not isinstance(text, str) or not text.strip():
            return self._blocked("文本不能为空")
        if len(text) > 2_000_000:
            return self._blocked("文本超过 2,000,000 字符限制")
        try:
            findings, safe_text = self._protect(text, extra_findings or [], semantic)
            digest = hashlib.sha256(text.encode()).hexdigest()
            summary = counts(findings)
            reference = self.store.create(safe_text=safe_text, output_path=None, source_digest=digest, counts=summary)
            return {"status": "approved", "counts": summary, "safe_reference": reference.token, "expires_at": reference.expires_at}
        except Exception:
            return self._blocked("识别服务或二次检查失败，已阻断")

    def _prepare_file(self, raw_path: str):
        """Use upstream parsing/HaS for both analysis and optional export.

        Container inspection supplements upstream text; it never substitutes
        for failed upstream parsing, OCR or recognition.
        """
        path = validate_source_path(raw_path, self.settings.allowed_roots, self.settings.max_file_bytes)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        parsed = self.redaction.upload_and_parse(path)
        text = parsed.get("content")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("上游解析或 OCR 未产生可验证文本")
        extra = verified_findings(text, parsed.get("entities", []), "redaction-everything-file")
        suffix = path.suffix.lower()
        if suffix in {".docx", ".pdf"}:
            inspected = inspect_source(path)
            missing = [line for line in inspected.splitlines() if line.strip() and line not in text]
            if missing:
                text += "\n" + "\n".join(missing)
        if len(text) > 2_000_000:
            raise ValueError("文件文本超限")
        findings, safe_text = self._protect(text, extra, True)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("源文件在处理期间已改变")
        return path, digest, text, findings, safe_text

    def scan_file(self, raw_path: str) -> dict:
        try:
            path, digest, _, findings, safe_text = self._prepare_file(raw_path)
            summary = counts(findings)
            reference = self.store.create(safe_text=safe_text, output_path=None,
                                          source_digest=digest, counts=summary)
            return {"status": "approved", "safe_reference": reference.token,
                    "counts": summary, "expires_at": reference.expires_at,
                    "file_type": path.suffix.lower().lstrip("."), "parser": "redaction-everything"}
        except Exception as exc:
            return self._blocked(f"文件读取或验证失败 ({type(exc).__name__})")

    def redact_file(self, raw_path: str) -> dict:
        output = None
        stage = "source-preparation"
        try:
            path, digest, text, findings, safe_text = self._prepare_file(raw_path)
            suffix = path.suffix.lower()
            stage = "semantic-review"
            uncertain = [item for item in findings
                          if item.entity_type in UNCERTAIN_SEMANTIC_TYPES
                          and item.score < SEMANTIC_EXPORT_THRESHOLD]
            if uncertain:
                raise ReviewRequiredError("存在低置信度语义实体，需人工确认后才能生成安全副本")
            original_values = [text[item.start:item.end] for item in findings]
            stage = "text-rescan"
            if self.detect(safe_text, approved_tokens=True):
                raise ValueError("安全文本二次检测未通过")
            # PrivacyGuard alone owns replacement and clean-copy generation.
            stage = "output-rebuild"
            is_document = suffix in {".pdf", ".docx"}
            output_suffix = suffix if is_document else ".txt"
            raw = rebuild_safe_file(safe_text, output_suffix)
            verified_text = verify_output(raw, output_suffix, original_values)
            stage = "file-rescan"
            if self.detect(verified_text, approved_tokens=True):
                raise ValueError("安全文件二次识别未通过")
            output = self.store.root / f"{secrets.token_hex(24)}{output_suffix}"
            output.write_bytes(raw)
            output.chmod(0o600)
            reference = self.store.create(safe_text=verified_text, output_path=output,
                source_digest=digest, counts=counts(findings))
            return {"status": "approved", "safe_reference": reference.token, "counts": counts(findings),
                    "file_type": suffix[1:], "output_kind": "safe-file",
                    "parser": "redaction-everything",
                    "layout": "reconstructed-text-only" if is_document else "sanitized-text",
                    "expires_at": reference.expires_at}
        except Exception as exc:
            if output:
                output.unlink(missing_ok=True)
            if isinstance(exc, ReviewRequiredError):
                return self._blocked(f"安全副本阻断：{stage}（需要人工确认）")
            return self._blocked(f"安全副本阻断：{stage} ({type(exc).__name__})")

    def get_safe_content(self, reference: str) -> dict:
        try:
            item = self.store.get(reference)
            if item.kind == "text" and item.safe_text is not None:
                return {"status": "approved", "kind": "text", "content": item.safe_text, "counts": item.counts}
            return {"status": "approved", "kind": "file", "path": item.output_path, "content": item.safe_text, "counts": item.counts}
        except (ReferenceError, OSError) as exc:
            return self._blocked(str(exc))

    async def secure_ask(self, safe_reference: str, task: str = "risk_summary") -> dict:
        try:
            from .secure_ask import secure_ask
            return await secure_ask(self, safe_reference, task)
        except Exception as exc:
            return self._blocked(f"受控调用初始化失败 ({type(exc).__name__})")

    async def process_and_ask(
        self,
        raw_path: str,
        task: str = "risk_summary",
        create_safe_copy: bool = False,
    ) -> dict:
        """Run the protected file workflow without exposing content or bearer references."""
        prepared = self.redact_file(raw_path) if create_safe_copy else self.scan_file(raw_path)
        if prepared.get("status") != "approved":
            return {
                "status": "blocked",
                "stage": "safe-copy" if create_safe_copy else "scan",
                "reason": prepared.get("reason", "隐私处理失败，已阻断"),
                "counts": {},
                "safe_file": None,
            }

        reference = str(prepared["safe_reference"])
        analysis = await self.secure_ask(reference, task)
        if analysis.get("status") != "approved":
            return {
                "status": "blocked",
                "stage": "secure-analysis",
                "reason": analysis.get("reason", "受控分析失败，已阻断"),
                "counts": prepared.get("counts", {}),
                "safe_file": None,
            }

        safe_file = None
        if create_safe_copy:
            try:
                approved = self.store.get(reference)
                if approved.kind == "file":
                    safe_file = {"kind": "file", "path": approved.output_path}
                else:
                    safe_file = {"kind": "sanitized-text", "path": None}
            except Exception as exc:
                return {
                    "status": "blocked",
                    "stage": "safe-copy-retrieval",
                    "reason": f"安全副本读取失败，已阻断 ({type(exc).__name__})",
                    "counts": prepared.get("counts", {}),
                    "safe_file": None,
                }
        return {
            "status": "approved",
            "answer": analysis["answer"],
            "task": analysis["task"],
            "guardrail": analysis["guardrail"],
            "counts": prepared.get("counts", {}),
            "file_type": prepared.get("file_type"),
            "safe_file": safe_file,
        }
