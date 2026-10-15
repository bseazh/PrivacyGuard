from __future__ import annotations

from service.redaction_core import detect_entities

from .models import Finding


def detect_with_rules(text: str) -> list[Finding]:
    return [Finding(item.type, item.start, item.end, item.confidence, "privacyguard-rule") for item in detect_entities(text)]


def merge_findings(*groups: list[Finding]) -> list[Finding]:
    candidates = [item for group in groups for item in group]
    candidates.sort(key=lambda item: (item.start, item.end))
    selected: list[Finding] = []
    for candidate in candidates:
        if selected and candidate.start < selected[-1].end:
            previous = selected.pop()
            winner = max((previous, candidate), key=lambda item: (item.score, item.end - item.start))
            selected.append(Finding(winner.entity_type, previous.start, max(previous.end, candidate.end), max(previous.score, candidate.score), "merged"))
        else:
            selected.append(candidate)
    return sorted(selected, key=lambda item: item.start)


def counts(findings: list[Finding]) -> dict[str, int]:
    output: dict[str, int] = {}
    for item in findings:
        output[item.entity_type] = output.get(item.entity_type, 0) + 1
    return output


def replace_with_tokens(text: str, findings: list[Finding]) -> str:
    counters: dict[str, int] = {}
    pieces: list[str] = []
    cursor = 0
    tokens: dict[tuple[str, str], str] = {}
    for item in findings:
        key = (item.entity_type, text[item.start:item.end])
        if key not in tokens:
            counters[item.entity_type] = counters.get(item.entity_type, 0) + 1
            tokens[key] = f"<{item.entity_type}_{counters[item.entity_type]:03d}>"
        pieces.extend((text[cursor:item.start], tokens[key]))
        cursor = item.end
    pieces.append(text[cursor:])
    return "".join(pieces)
