from __future__ import annotations

import io
from dataclasses import asdict

from .pseudonym import build_replacements


class PdfRedactionError(RuntimeError):
    pass


def _fit_font_size(fitz, text: str, width: float, height: float) -> float:
    size = max(4.0, min(12.0, height * 0.72))
    while size > 4.0 and fitz.get_text_length(text, fontname="china-s", fontsize=size) > max(1.0, width - 2):
        size -= 0.5
    return size


def redact_pdf_bytes(raw: bytes, entities: list[dict], mode: str = "semantic") -> tuple[bytes, dict]:
    """Securely remove exact text matches and write stable replacements in their place.

    This intentionally supports PDFs with a searchable text layer only. It refuses a
    partial result so a scanned PDF or extraction-coordinate mismatch cannot be
    mistaken for a safely redacted document.
    """
    try:
        import fitz
    except ImportError as exc:
        raise PdfRedactionError("缺少 PyMuPDF；请按安装文档安装 PDF 脱敏依赖") from exc

    replacements = build_replacements(entities, mode)
    if not replacements:
        raise PdfRedactionError("没有已确认的脱敏实体")

    try:
        document = fitz.open(stream=raw, filetype="pdf")
    except Exception as exc:
        raise PdfRedactionError(f"无法打开 PDF：{exc}") from exc

    matches: dict[tuple[str, str], list[tuple[int, object]]] = {}
    try:
        for item in replacements:
            key = (item.type, item.value)
            locations: list[tuple[int, object]] = []
            for page_number, page in enumerate(document):
                locations.extend((page_number, rect) for rect in page.search_for(item.value))
            matches[key] = locations

        missing = [item.value for item in replacements if not matches[(item.type, item.value)]]
        if missing:
            raise PdfRedactionError(
                f"PDF 中有 {len(missing)} 个实体无法精确定位。"
                "这通常是扫描件或文本编码差异；为避免伪脱敏，已停止导出。"
            )

        insertions: dict[int, list[tuple[object, str]]] = {}
        for item in replacements:
            for page_number, rect in matches[(item.type, item.value)]:
                page = document[page_number]
                page.add_redact_annot(rect, fill=(1, 1, 1))
                insertions.setdefault(page_number, []).append((rect, item.replacement))

        for page_number, page_insertions in insertions.items():
            page = document[page_number]
            page.apply_redactions()
            for rect, replacement in page_insertions:
                fontsize = _fit_font_size(fitz, replacement, rect.width, rect.height)
                target = fitz.Rect(rect.x0, rect.y0, max(rect.x1, rect.x0 + 8), rect.y1 + max(2, rect.height * 0.15))
                result = page.insert_textbox(
                    target,
                    replacement,
                    fontname="china-s",
                    fontsize=fontsize,
                    color=(0, 0, 0),
                    align=fitz.TEXT_ALIGN_CENTER,
                    overlay=True,
                )
                if result < 0:
                    short = replacement[:4]
                    page.insert_text((rect.x0, rect.y1 - 1), short, fontname="china-s", fontsize=4, color=(0, 0, 0), overlay=True)

        document.set_metadata({})
        output = io.BytesIO()
        document.save(output, garbage=4, clean=True, deflate=True)
        redacted = output.getvalue()
    finally:
        document.close()

    verification = fitz.open(stream=redacted, filetype="pdf")
    try:
        leaked = []
        for item in replacements:
            if any(page.search_for(item.value) for page in verification):
                leaked.append(item.value)
        if leaked:
            raise PdfRedactionError(f"安全校验失败，输出中仍可搜索到原文：{'、'.join(leaked[:5])}")
    finally:
        verification.close()

    mapping = {
        item.replacement: {
            "type": item.type,
            "value": item.value,
            "occurrences": len(matches[(item.type, item.value)]),
        }
        for item in replacements
    }
    return redacted, {"mode": mode, "mapping": mapping, "replacements": [asdict(item) for item in replacements]}
