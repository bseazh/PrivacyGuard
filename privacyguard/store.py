from __future__ import annotations

import json
import logging
import secrets
import time
from dataclasses import asdict
from pathlib import Path

from .models import SafeReference
from .security import private_directory
from .security import mask_secret, sha256_file


logger = logging.getLogger("privacyguard.references")


class ReferenceError(ValueError):
    pass


class SafeReferenceStore:
    def __init__(self, root: Path, ttl_seconds: int):
        self.root = private_directory(root / "approved")
        self.ttl_seconds = ttl_seconds

    def create(self, *, safe_text: str | None, output_path: Path | None, source_digest: str, counts: dict[str, int]) -> SafeReference:
        now = time.time()
        reference = SafeReference(
            token=secrets.token_urlsafe(32),
            created_at=now,
            expires_at=now + self.ttl_seconds,
            kind="file" if output_path else "text",
            output_path=str(output_path.resolve()) if output_path else None,
            safe_text=safe_text,
            source_digest=source_digest,
            counts=counts,
            output_digest=sha256_file(output_path) if output_path else None,
        )
        target = self.root / f"{reference.token}.json"
        target.write_text(json.dumps(asdict(reference), ensure_ascii=False), encoding="utf-8")
        target.chmod(0o600)
        logger.debug("safe_reference_created reference=%s kind=%s ttl_seconds=%d", mask_secret(reference.token), reference.kind, self.ttl_seconds)
        return reference

    def get(self, token: str) -> SafeReference:
        if not token or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for char in token):
            raise ReferenceError("安全引用无效")
        target = self.root / f"{token}.json"
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
            reference = SafeReference(**data)
        except (OSError, ValueError, TypeError) as exc:
            raise ReferenceError("安全引用不存在或已失效") from exc
        if reference.token != token or reference.expires_at < time.time():
            target.unlink(missing_ok=True)
            raise ReferenceError("安全引用不存在或已过期")
        if reference.output_path:
            if Path(reference.output_path).is_symlink():
                raise ReferenceError("安全文件被替换为符号链接")
            output = Path(reference.output_path).resolve(strict=True)
            if self.root not in output.parents:
                raise ReferenceError("安全文件不属于批准目录")
            if not reference.output_digest or sha256_file(output) != reference.output_digest:
                raise ReferenceError("安全文件已被修改，必须重新扫描")
        logger.debug("safe_reference_accessed reference=%s kind=%s", mask_secret(token), reference.kind)
        return reference
