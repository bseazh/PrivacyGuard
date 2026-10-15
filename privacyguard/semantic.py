from __future__ import annotations

import json
import math
import os
import re
import subprocess
from pathlib import Path

from .models import Finding
from .rules import merge_findings

ALIASES = {"ORG": "ORGANIZATION", "INSTITUTION_NAME": "ORGANIZATION", "COMPANY_NAME": "ORGANIZATION", "ID_CARD": "ID_NUMBER", "EMAIL_ADDRESS": "EMAIL", "PHONE_NUMBER": "PHONE", "BANK_ACCOUNT": "BANK_CARD"}

GENERIC_PROJECT_TERMS = {
    "合同", "协议", "补充协议", "合作协议", "采购合同", "销售合同", "服务合同",
    "测试", "项目", "系统", "产品", "材料", "货物", "问题", "现象", "原装货",
    "库存同步异常",
}


def windows(text: str, size: int = 2400, overlap: int = 300):
    for offset in range(0, len(text), size - overlap):
        yield offset, text[offset:offset + size]
        if offset + size >= len(text):
            break


def verified_findings(text: str, entities: list[dict], source: str, offset: int = 0) -> list[Finding]:
    result = []
    for item in entities:
        start, end = int(item["start"]), int(item["end"])
        if not 0 <= start < end <= len(text) or text[start:end] != item.get("text", item.get("value")):
            raise ValueError("语义识别实体区间无法验证")
        score = item.get("confidence")
        kind = ALIASES.get(str(item["type"]), str(item["type"]))
        value = text[start:end]
        # A bare generic business word is not a project identifier. Keep
        # named projects, even when they do not have an explicit label.
        if kind == "PROJECT" and value.strip() in GENERIC_PROJECT_TERMS:
            continue
        score = float(score) if score is not None else 0.75
        if not re.fullmatch(r"[A-Z_]+", kind) or not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("语义识别类型或置信度无效")
        result.append(Finding(kind, offset + start, offset + end, score, source))
    return result


class SemanticEnsemble:
    def __init__(self, redaction):
        self.redaction = redaction

    def analyze(self, text: str) -> list[Finding]:
        findings = []
        for offset, chunk in windows(text):
            payload = self.redaction.analyze_text(chunk)
            findings.extend(verified_findings(chunk, payload, "redaction-everything", offset))
        python = os.getenv("PRIVACYGUARD_MLX_PYTHON")
        if python:
            root = Path(__file__).resolve().parents[1]
            result = subprocess.run(
                [python, "-m", "privacyguard.mlx_worker"], cwd=root,
                input=json.dumps({"text": text}), capture_output=True, text=True, timeout=600,
            )
            if result.returncode:
                raise ValueError("MLX 语义识别失败，已阻断")
            findings.extend(verified_findings(text, json.loads(result.stdout), "mlx"))
        return merge_findings(findings)
