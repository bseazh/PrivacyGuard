from __future__ import annotations

import base64
from pathlib import Path
from email import policy
from email.parser import BytesParser
import tempfile
import uuid

import httpx


class RedactionEverythingError(RuntimeError):
    pass


class RedactionEverythingAdapter:
    """HTTP-only adapter for a separately installed, licensed local instance."""

    def __init__(self, base_url: str, token: str | None = None, timeout: float = 180.0,
                 ocr_url: str = "http://127.0.0.1:8082"):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.ocr_url = ocr_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}

    def health(self) -> dict:
        try:
            with httpx.Client(trust_env=False, timeout=5.0) as client:
                response = client.get(f"{self.base_url}/health/services", headers=self.headers)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RedactionEverythingError("RedactionEverything 不可用") from exc

    def analyze_text(self, text: str) -> list[dict]:
        with tempfile.TemporaryDirectory(prefix="privacyguard-ner-") as directory:
            path = Path(directory) / "input.txt"
            path.write_text(text, encoding="utf-8")
            parsed = self.upload_and_parse(path)
        if parsed["content"] != text:
            raise RedactionEverythingError("上游文本解析发生变化，无法验证区间")
        return parsed["entities"]

    def execute_and_download(self, file_id: str, text: str, findings) -> bytes:
        entities = [{"id": uuid.uuid4().hex, "type": item.entity_type, "text": text[item.start:item.end], "start": item.start, "end": item.end, "confidence": item.score, "selected": True} for item in findings]
        try:
            with httpx.Client(trust_env=False, timeout=self.timeout) as client:
                response = client.post(f"{self.base_url}/api/v1/redaction/execute", headers=self.headers, json={
                    "file_id": file_id, "entities": entities,
                    "config": {"replacement_mode": "structured", "entity_types": sorted({item.entity_type for item in findings})},
                })
                response.raise_for_status()
                response.json()["output_file_id"]
                downloaded = client.get(f"{self.base_url}/api/v1/files/{file_id}/download", headers=self.headers, params={"redacted": "true"})
                downloaded.raise_for_status()
                if not downloaded.content or len(downloaded.content) > 50 * 1024 * 1024:
                    raise ValueError("invalid output size")
                return downloaded.content
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise RedactionEverythingError("脱敏执行或安全文件下载失败") from exc

    def _upload_parse_ner(self, path: Path) -> dict:
        """Upload one file and return the upstream parse + HaS response."""
        with httpx.Client(trust_env=False, timeout=self.timeout) as client:
            with path.open("rb") as stream:
                response = client.post(
                    f"{self.base_url}/api/v1/files/upload",
                    headers=self.headers,
                    files={"file": (f"privacyguard-input{path.suffix.lower()}", stream, "application/octet-stream")},
                )
            response.raise_for_status()
            upload = response.json()
            file_id = str(upload["file_id"])
            parsed = client.get(f"{self.base_url}/api/v1/files/{file_id}/parse", headers=self.headers)
            parsed.raise_for_status()
            ner = client.get(f"{self.base_url}/api/v1/files/{file_id}/ner", headers=self.headers)
            ner.raise_for_status()
        result = parsed.json()
        ner_result = ner.json()
        if (not isinstance(result, dict) or not isinstance(result.get("content"), str)
                or not isinstance(ner_result, dict) or not isinstance(ner_result.get("entities"), list)
                or ner_result.get("recognition_failed")):
            raise ValueError("RedactionEverything recognition failed")
        return {
            "file_id": file_id,
            "file_type": upload.get("file_type"),
            "content": result.get("content", ""),
            "is_scanned": bool(result.get("is_scanned")),
            "page_count": result.get("page_count"),
            "pages": result.get("pages"),
            "entities": ner_result.get("entities", []),
        }

    def _ocr_pdf_pages(self, path: Path, page_count: int) -> tuple[list[str], dict]:
        """Run the local RedactionEverything OCR service page by page.

        The OCR service returns ordered text boxes, not a document body. We
        rebuild a page-preserving body and refuse partial coverage. HaS then
        runs against that exact temporary TXT body through the normal upstream
        parse/NER endpoints.
        """
        try:
            import fitz
        except ImportError as exc:  # pragma: no cover - dependency is required
            raise ValueError("PDF OCR 需要 PyMuPDF") from exc
        if not isinstance(page_count, int) or page_count < 1:
            raise ValueError("PDF 页数无法验证")
        pages: list[str] = []
        page_stats: list[dict] = []
        with fitz.open(path) as document, httpx.Client(trust_env=False, timeout=self.timeout) as client:
            if len(document) != page_count:
                raise ValueError("PDF 页数在解析期间发生变化")
            for page_number, page in enumerate(document, start=1):
                pixmap = page.get_pixmap(matrix=fitz.Matrix(150 / 72, 150 / 72), alpha=False)
                encoded = base64.b64encode(pixmap.tobytes("png")).decode("ascii")
                # PP-StructureV3 is the enabled CPU-compatible OCR route on
                # this installation; PaddleOCR-VL `/ocr` may be disabled.
                response = client.post(f"{self.ocr_url}/structure", json={"image": encoded})
                response.raise_for_status()
                payload = response.json()
                boxes = payload.get("boxes") if isinstance(payload, dict) else None
                if not isinstance(boxes, list):
                    raise ValueError(f"OCR 第 {page_number} 页返回格式无效")
                ordered = []
                for box in boxes:
                    if not isinstance(box, dict) or not isinstance(box.get("text"), str):
                        continue
                    value = box["text"].strip()
                    if not value:
                        continue
                    try:
                        y = float(box.get("y", 0))
                        x = float(box.get("x", 0))
                    except (TypeError, ValueError):
                        raise ValueError(f"OCR 第 {page_number} 页坐标无效")
                    ordered.append((y, x, value))
                ordered.sort(key=lambda item: (item[0], item[1]))
                page_text = "\n".join(item[2] for item in ordered).strip()
                if not page_text:
                    raise ValueError(f"OCR 第 {page_number} 页没有可验证文本")
                pages.append(page_text)
                page_stats.append({"page": page_number, "box_count": len(ordered), "text_chars": len(page_text)})
        return pages, {"complete": len(pages) == page_count, "page_count": page_count, "pages": page_stats}

    def upload_and_parse(self, path: Path) -> dict:
        try:
            suffix = path.suffix.lower()
            if suffix == ".eml":
                raw = path.read_bytes()
                message = BytesParser(policy=policy.default).parsebytes(raw)
                if (message.is_multipart() or message.get_content_type() != "text/plain"
                        or message.get("Content-Transfer-Encoding", "7bit").lower() not in {"7bit", "8bit"}
                        or b"=?" in raw):
                    raise ValueError("编码邮件或 MIME 附件尚未验证")
            # The upstream parser supports TXT, but not these extension aliases.
            upload_suffix = ".txt" if suffix in {".md", ".markdown", ".eml"} else suffix
            source = path
            temporary_alias = None
            if upload_suffix != suffix:
                temporary_alias = tempfile.NamedTemporaryFile(prefix="privacyguard-input-", suffix=upload_suffix, delete=False)
                temporary_alias.write(path.read_bytes())
                temporary_alias.close()
                source = Path(temporary_alias.name)
            try:
                parsed = self._upload_parse_ner(source)
            finally:
                if temporary_alias is not None:
                    source.unlink(missing_ok=True)
            content = parsed.get("content", "")
            if suffix == ".pdf" and (parsed.get("is_scanned") or not content.strip()):
                pages, coverage = self._ocr_pdf_pages(path, int(parsed.get("page_count") or 0))
                ocr_text = "\n\n".join(pages)
                with tempfile.TemporaryDirectory(prefix="privacyguard-ocr-text-") as directory:
                    ocr_path = Path(directory) / "ocr.txt"
                    ocr_path.write_text(ocr_text, encoding="utf-8")
                    ocr_result = self._upload_parse_ner(ocr_path)
                if ocr_result.get("content") != ocr_text:
                    raise ValueError("OCR 文本经上游解析后发生变化")
                parsed.update({
                    "content": ocr_text,
                    "entities": ocr_result.get("entities", []),
                    "pages": pages,
                    "page_count": len(pages),
                    "is_scanned": True,
                    "ocr_complete": bool(coverage.get("complete")),
                    "ocr_coverage": coverage,
                })
            return parsed
        except (httpx.HTTPError, KeyError, TypeError, ValueError, OSError, RuntimeError) as exc:
            raise RedactionEverythingError("RedactionEverything 上传或解析失败，已阻断处理") from exc
