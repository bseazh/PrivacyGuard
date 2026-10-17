from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _paths(raw: str | None) -> tuple[Path, ...]:
    if raw:
        return tuple(Path(item).expanduser().resolve() for item in raw.split(os.pathsep) if item.strip())
    home = Path.home()
    return tuple(path.resolve() for path in (home / "Documents", home / "Desktop", home / "Downloads") if path.exists())


@dataclass(frozen=True)
class Settings:
    allowed_roots: tuple[Path, ...]
    data_dir: Path
    max_file_bytes: int
    reference_ttl_seconds: int
    presidio_url: str
    redaction_url: str
    redaction_token: str | None
    redaction_ocr_url: str = "http://127.0.0.1:8082"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            allowed_roots=_paths(os.getenv("PRIVACYGUARD_ALLOWED_ROOTS")),
            data_dir=Path(os.getenv("PRIVACYGUARD_DATA_DIR", "~/.privacyguard")).expanduser().resolve(),
            max_file_bytes=int(os.getenv("PRIVACYGUARD_MAX_FILE_BYTES", str(50 * 1024 * 1024))),
            reference_ttl_seconds=int(os.getenv("PRIVACYGUARD_REFERENCE_TTL", "900")),
            presidio_url=os.getenv("PRIVACYGUARD_PRESIDIO_URL", "http://127.0.0.1:5002").rstrip("/"),
            redaction_url=os.getenv("PRIVACYGUARD_REDACTION_BASE_URL", "http://127.0.0.1:8000").rstrip("/"),
            redaction_token=os.getenv("PRIVACYGUARD_REDACTION_TOKEN") or None,
            redaction_ocr_url=os.getenv("PRIVACYGUARD_REDACTION_OCR_URL", "http://127.0.0.1:8082").rstrip("/"),
        )
