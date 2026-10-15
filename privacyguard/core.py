from __future__ import annotations

import hashlib
import re
import secrets
import subprocess
from pathlib import Path

from .adapters.presidio import PresidioAdapter, PresidioUnavailable
from .adapters.redaction_everything import RedactionEverythingAdapter, RedactionEverythingError
from .config import Settings
from .models import Finding
from .semantic import SemanticEnsemble, windows
from .safe_files import inspect_source, rebuild_safe_file, verify_output
from .parsers import extract_local_text
from .rules import counts, detect_with_rules, merge_findings, replace_with_tokens
from .security import SecurityError, validate_source_path
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
        findings = detect_with_rules(text)
        for offset, chunk in windows(text):
            for item in self.presidio.analyze(chunk):
                if not 0 <= item.start < item.end <= len(chunk):
                    raise ValueError("Presidio 实体区间无效")
                findings.append(Finding(item.entity_type, offset + item.start, offset + item.end, item.score, item.source))
        if semantic:
            findings.extend(self.semantic.analyze(text))
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

    def scan_file(self, raw_path: str) -> dict:
        try:
            path = validate_source_path(raw_path, self.settings.allowed_roots, self.settings.max_file_bytes)
            if path.suffix.lower() == ".pdf":
                parsed = self.redaction.upload_and_parse(path)
                text = str(parsed.get("content") or "")
                extra_findings: list[Finding] = []
                parser = "redaction-everything"
                if not text.strip():
                    local_text = extract_local_text(path)
                    if local_text.strip():
                        text = local_text
                        parser = "redaction-everything+local-text-layer"
                    else:
                        return self._blocked("扫描 PDF 尚未产生可验证文本，已阻断")
                else:
                    type_aliases = {"ID_CARD": "ID_NUMBER", "ORG": "ORGANIZATION"}
                    for item in parsed.get("entities", []):
                        start, end = int(item["start"]), int(item["end"])
                        if not (0 <= start < end <= len(text)) or text[start:end] != item.get("text"):
                            raise ValueError("RedactionEverything 实体位置无法验证")
                        confidence = item.get("confidence")
                        extra_findings.append(Finding(
                            type_aliases.get(str(item["type"]), str(item["type"])),
                            start,
                            end,
                            float(confidence) if confidence is not None else 0.75,
                            "redaction-everything",
                        ))
            else:
                text = inspect_source(path) if path.suffix.lower() == ".docx" else extract_local_text(path)
                extra_findings = []
                parser = "local"
            result = self.scrub_text(text, extra_findings, semantic=True)
            result.update({"file_type": path.suffix.lower().lstrip("."), "parser": parser})
            return result
        except Exception as exc:
            return self._blocked(f"文件读取或验证失败 ({type(exc).__name__})")

    def redact_file(self, raw_path: str) -> dict:
        output = None
        stage = "source-inspection"
        try:
            path = validate_source_path(raw_path, self.settings.allowed_roots, self.settings.max_file_bytes)
            suffix = path.suffix.lower()
            if suffix in {".txt", ".md", ".markdown", ".eml"}:
                result = self.scan_file(str(path))
                if result.get("status") == "approved":
                    result["output_kind"] = "safe-text-reference"
                    result["layout"] = "sanitized-text"
                return result
            if suffix not in {".pdf", ".docx"}:
                raise ValueError("安全输出仅支持 TXT/Markdown/EML/PDF/DOCX")
            text = inspect_source(path)
            if not text.strip() or len(text) > 2_000_000:
                raise ValueError("文件文本为空或超限")
            stage = "semantic-detection"
            findings, safe_text = self._protect(text, [], True)
            uncertain = [item for item in findings
                          if item.entity_type in UNCERTAIN_SEMANTIC_TYPES
                          and item.score < SEMANTIC_EXPORT_THRESHOLD]
            if uncertain:
                raise ReviewRequiredError("存在低置信度语义实体，需人工确认后才能生成安全副本")
            original_values = [text[item.start:item.end] for item in findings]
            stage = "text-rescan"
            if self.detect(safe_text, approved_tokens=True):
                raise ValueError("安全文本二次检测未通过")
            stage = "upstream-upload"
            parsed = self.redaction.upload_and_parse(path)
            # Upstream offsets belong to its own parser; re-detect that exact text.
            upstream_text = str(parsed.get("content") or "")
            upstream_findings = self.detect(upstream_text) if upstream_text.strip() else findings
            stage = "upstream-export"
            downloaded = self.redaction.execute_and_download(parsed["file_id"], upstream_text or text, upstream_findings)
            if suffix == ".pdf" and not downloaded.startswith(b"%PDF-"):
                raise ValueError("上游下载文件格式无效")
            if suffix == ".docx" and not downloaded.startswith(b"PK"):
                raise ValueError("上游下载文件格式无效")
            # Never publish the downloaded package: rebuild a clean text-only copy.
            stage = "output-rebuild"
            raw = rebuild_safe_file(safe_text, suffix)
            verified_text = verify_output(raw, suffix, original_values)
            stage = "file-rescan"
            if self.detect(verified_text, approved_tokens=True):
                raise ValueError("安全文件二次识别未通过")
            output = self.store.root / f"{secrets.token_hex(24)}{suffix}"
            output.write_bytes(raw)
            output.chmod(0o600)
            reference = self.store.create(safe_text=verified_text, output_path=output,
                source_digest=hashlib.sha256(path.read_bytes()).hexdigest(), counts=counts(findings))
            return {"status": "approved", "safe_reference": reference.token, "counts": counts(findings),
                    "file_type": suffix[1:], "layout": "reconstructed-text-only", "expires_at": reference.expires_at}
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
