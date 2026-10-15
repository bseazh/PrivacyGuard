from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Finding:
    entity_type: str
    start: int
    end: int
    score: float
    source: str

    def public_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class SafeReference:
    token: str
    created_at: float
    expires_at: float
    kind: str
    output_path: str | None
    safe_text: str | None
    source_digest: str
    counts: dict[str, int]
    output_digest: str | None = None
