from __future__ import annotations

from pathlib import Path
import tempfile
import uuid

import httpx


class RedactionEverythingError(RuntimeError):
    pass


class RedactionEverythingAdapter:
    """HTTP-only adapter for a separately installed, licensed local instance."""

    def __init__(self, base_url: str, token: str | None = None, timeout: float = 180.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
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

    def upload_and_parse(self, path: Path) -> dict:
        try:
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
                parsed = client.get(
                    f"{self.base_url}/api/v1/files/{file_id}/parse",
                    headers=self.headers,
                )
                ner = client.get(
                    f"{self.base_url}/api/v1/files/{file_id}/ner",
                    headers=self.headers,
                )
            parsed.raise_for_status()
            ner.raise_for_status()
            result = parsed.json()
            ner_result = ner.json()
            if ner_result.get("recognition_failed"):
                raise ValueError("RedactionEverything recognition failed")
            return {
                "file_id": file_id,
                "file_type": upload.get("file_type"),
                "content": result.get("content", ""),
                "is_scanned": bool(result.get("is_scanned")),
                "entities": ner_result.get("entities", []),
            }
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise RedactionEverythingError("RedactionEverything 上传或解析失败，已阻断处理") from exc
