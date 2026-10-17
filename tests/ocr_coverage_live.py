"""Opt-in real OCR + HaS + PrivacyGuard acceptance; fictional inputs only.

Run with .venv/bin/python tests/ocr_coverage_live.py while local services run.
Only coverage counts are printed; no text or bearer references are logged.
"""
import json
import tempfile
from dataclasses import replace
from pathlib import Path

import fitz

from privacyguard.adapters.redaction_everything import RedactionEverythingAdapter, RedactionEverythingError
from privacyguard.config import Settings
from privacyguard.core import PrivacyGuard


def make_scan(path: Path, *, blank_tail: bool = False) -> None:
    lines = ["SCAN PAGE ONE\nContract Party: Tang San\nPhone: 13800138000",
             "" if blank_tail else "SCAN PAGE TWO\nEmail: alice@example.com\nAmount: CNY 100000"]
    with fitz.open() as output:
        for text in lines:
            with fitz.open() as source:
                page = source.new_page()
                page.insert_text((60, 120), text, fontsize=20)
                image = page.get_pixmap(matrix=fitz.Matrix(150 / 72, 150 / 72), alpha=False)
                target = output.new_page()
                target.insert_image(target.rect, stream=image.tobytes("png"))
        output.save(path)


def main() -> None:
    settings = Settings.from_env()
    adapter = RedactionEverythingAdapter(settings.redaction_url, settings.redaction_token,
                                        timeout=600, ocr_url=settings.redaction_ocr_url)
    with tempfile.TemporaryDirectory(prefix="privacyguard-ocr-acceptance-") as directory:
        root = Path(directory).resolve()
        scan = root / "two-pages.pdf"
        make_scan(scan)
        parsed = adapter.upload_and_parse(scan)
        assert parsed.get("ocr_complete") is True
        assert parsed["page_count"] == len(parsed["pages"]) == 2
        assert "\n\n".join(parsed["pages"]) == parsed["content"]
        assert "SCAN PAGE ONE" in parsed["pages"][0]
        assert "SCAN PAGE TWO" in parsed["pages"][1]
        assert "13800138000" in parsed["pages"][0]
        assert "alice@example.com" in parsed["pages"][1]
        core = PrivacyGuard(replace(settings, allowed_roots=(root,), data_dir=root / "state"))
        result = core.scan_file(str(scan))
        assert result["status"] == "approved", result.get("reason")
        safe = core.store.get(result["safe_reference"]).safe_text
        assert "13800138000" not in safe and "alice@example.com" not in safe
        blank = root / "blank-tail.pdf"
        make_scan(blank, blank_tail=True)
        try:
            adapter.upload_and_parse(blank)
        except RedactionEverythingError:
            pass
        else:
            raise AssertionError("Blank OCR page was accepted")
        print(json.dumps({"ocr_complete": True, "pages": parsed["ocr_coverage"]["pages"],
                          "scan_approved": True, "blank_page_blocked": True,
                          "counts": result["counts"]}))


if __name__ == "__main__":
    main()
