from __future__ import annotations

import httpx

from privacyguard.models import Finding


class PresidioUnavailable(RuntimeError):
    pass


class PresidioAdapter:
    def __init__(self, base_url: str, timeout: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def health(self) -> bool:
        try:
            with httpx.Client(trust_env=False, timeout=3.0) as client:
                response = client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def analyze(self, text: str) -> list[Finding]:
        try:
            with httpx.Client(trust_env=False, timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/analyze",
                    json={"text": text, "language": "zh", "score_threshold": 0.5},
                )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                raise ValueError("Presidio 返回格式无效")
            return [
                Finding(str(item["entity_type"]), int(item["start"]), int(item["end"]), float(item["score"]), "presidio")
                for item in payload
            ]
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise PresidioUnavailable("Presidio 检测服务不可用或返回无效，已阻断处理") from exc
