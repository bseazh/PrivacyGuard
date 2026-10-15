from __future__ import annotations

import hashlib
import os
from pathlib import Path


SUPPORTED_SUFFIXES = {".txt", ".md", ".markdown", ".eml", ".docx", ".pdf"}


class SecurityError(ValueError):
    pass


def validate_source_path(raw_path: str | Path, allowed_roots: tuple[Path, ...], max_bytes: int) -> Path:
    requested = Path(raw_path).expanduser()
    if not requested.is_absolute():
        raise SecurityError("只接受绝对文件路径")
    current = Path(requested.anchor)
    for part in requested.parts[1:]:
        current = current / part
        if current.is_symlink():
            raise SecurityError("拒绝符号链接路径")
    resolved = requested.resolve(strict=True)
    if not resolved.is_file():
        raise SecurityError("文件不存在或不是普通文件")
    if not any(resolved == root or root in resolved.parents for root in allowed_roots):
        raise SecurityError("文件不在允许读取的目录中")
    if resolved.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise SecurityError(f"暂不支持 {resolved.suffix or '无扩展名'} 文件")
    size = resolved.stat().st_size
    if size <= 0 or size > max_bytes:
        raise SecurityError(f"文件大小必须在 1 到 {max_bytes} 字节之间")
    return resolved


def private_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass
    return path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def mask_secret(value: str, visible: int = 4) -> str:
    """Return a diagnostic-safe identifier without exposing a bearer token."""
    if not value:
        return "<empty>"
    if len(value) <= visible * 2:
        return "*" * len(value)
    return f"{value[:visible]}...{value[-visible:]}"
