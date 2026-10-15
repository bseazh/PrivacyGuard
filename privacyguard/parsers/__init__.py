from __future__ import annotations

from pathlib import Path

from service.redaction_core import extract_text


def extract_local_text(path: Path) -> str:
    return extract_text(path)
