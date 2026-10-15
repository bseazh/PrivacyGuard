from __future__ import annotations

import re
import subprocess
import zipfile
from datetime import date
from dataclasses import asdict, dataclass
from pathlib import Path
from xml.etree import ElementTree


@dataclass(frozen=True)
class Entity:
    type: str
    value: str
    start: int
    end: int
    confidence: float
    source: str = "rule"


# Ordered from the most specific formats to the more general ones.
PATTERNS: tuple[tuple[str, str, float], ...] = (
    ("ID_NUMBER", r"(?<![0-9Xx])[1-9][0-9]{5}(?:19|20)[0-9]{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12][0-9]|3[01])[0-9]{3}[0-9Xx](?![0-9Xx])", 0.99),
    ("PHONE", r"(?<![0-9])1[3-9][0-9]{9}(?![0-9])", 0.99),
    ("EMAIL", r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![A-Za-z0-9.-])", 0.99),
    ("BANK_CARD", r"(?<![0-9])(?:[0-9]{4}[ -]?){3,5}[0-9]{0,4}(?![0-9])", 0.96),
    ("CASE_NUMBER", r"(?<![\w])(?:[（(]20[0-9]{2}[)）]|20[0-9]{2})[\u4e00-\u9fffA-Za-z]{1,8}[0-9]{1,8}号?(?![\w])", 0.86),
    ("CONTRACT_NUMBER", r"(?<![\w])(?:合同|协议|委托|案)编号[：: ]?[A-Za-z0-9][A-Za-z0-9._/-]{3,}(?![\w])", 0.92),
)


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".eml", ".csv", ".json", ".ics", ".vcf"}:
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".docx":
        with zipfile.ZipFile(path) as archive:
            xml = archive.read("word/document.xml")
        root = ElementTree.fromstring(xml)
        paragraphs: list[str] = []
        for paragraph in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
            paragraphs.append("".join(node.text or "" for node in paragraph.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")))
        return "\n".join(paragraphs)
    if suffix == ".pdf":
        result = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True, check=False)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "pdftotext failed")
        return result.stdout
    raise ValueError(f"unsupported P0 file type: {path.suffix or '<none>'}")


def detect_entities(text: str) -> list[Entity]:
    candidates: list[Entity] = []
    for entity_type, pattern, confidence in PATTERNS:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            if entity_type == "ID_NUMBER" and not is_valid_china_id(match.group(0)):
                continue
            candidates.append(Entity(entity_type, match.group(0), match.start(), match.end(), confidence))
    # Keep the highest-confidence, longest entity for overlapping matches.
    candidates.sort(key=lambda item: (-item.confidence, -(item.end - item.start), item.start))
    selected: list[Entity] = []
    for candidate in candidates:
        if any(candidate.start < item.end and item.start < candidate.end for item in selected):
            continue
        selected.append(candidate)
    return sorted(selected, key=lambda item: item.start)


def is_valid_china_id(value: str) -> bool:
    """Validate an 18-digit mainland China citizen ID without exposing it."""
    if not re.fullmatch(r"[1-9][0-9]{16}[0-9Xx]", value):
        return False
    try:
        date.fromisoformat(f"{value[6:10]}-{value[10:12]}-{value[12:14]}")
    except ValueError:
        return False
    weights = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
    check_codes = "10X98765432"
    expected = check_codes[sum(int(number) * weight for number, weight in zip(value[:17], weights)) % 11]
    return value[-1].upper() == expected


def tokenize(text: str, entities: list[Entity]) -> tuple[str, dict[str, dict[str, str]]]:
    counters: dict[str, int] = {}
    mapping: dict[str, dict[str, str]] = {}
    pieces: list[str] = []
    cursor = 0
    for entity in entities:
        counters[entity.type] = counters.get(entity.type, 0) + 1
        token = f"<{entity.type}_{counters[entity.type]:03d}>"
        pieces.append(text[cursor : entity.start])
        pieces.append(token)
        mapping[token] = {"type": entity.type, "value": entity.value}
        cursor = entity.end
    pieces.append(text[cursor:])
    return "".join(pieces), mapping


def scan_file(path: Path) -> dict:
    text = extract_text(path)
    entities = detect_entities(text)
    redacted, mapping = tokenize(text, entities)
    return {"file": str(path), "characters": len(text), "entities": [asdict(item) for item in entities], "mapping": mapping, "redacted_text": redacted}
