from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from service.redaction_core import detect_entities, is_valid_china_id

try:
    from docx import Document
    from reportlab.pdfgen import canvas
    from privacyguard.config import Settings
    from privacyguard.core import PrivacyGuard
    from privacyguard.models import Finding
    from privacyguard.security import SecurityError, mask_secret, validate_source_path
    from privacyguard.store import ReferenceError, SafeReferenceStore
    CORE_TEST_DEPENDENCIES = True
except ModuleNotFoundError:
    CORE_TEST_DEPENDENCIES = False


class FakePresidio:
    def analyze(self, text: str) -> list[Finding]:
        findings = []
        for needle, kind in (("alice@example.com", "EMAIL_ADDRESS"), ("13800138000", "PHONE_NUMBER")):
            start = text.find(needle)
            if start >= 0:
                findings.append(Finding(kind, start, start + len(needle), 0.9, "presidio"))
        return findings


@unittest.skipUnless(CORE_TEST_DEPENDENCIES, "PrivacyGuard Core test dependencies are installed in .venv")
class PrivacyGuardCoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.settings = Settings(
            allowed_roots=(self.root,), data_dir=self.root / "state", max_file_bytes=1024 * 1024,
            reference_ttl_seconds=60, presidio_url="http://127.0.0.1:1", redaction_url="http://127.0.0.1:1", redaction_token=None,
        )
        self.core = PrivacyGuard(self.settings, presidio=FakePresidio())
        class NoSemantic:
            def analyze(self, text):
                return []
        self.core.semantic = NoSemantic()

    def tearDown(self):
        self.temp.cleanup()

    def test_scrubs_and_requires_safe_reference(self):
        original = "联系 alice@example.com 或 13800138000，身份证 11010519491231002X。"
        result = self.core.scrub_text(original)
        self.assertEqual(result["status"], "approved")
        self.assertNotIn("content", result)
        safe = self.core.get_safe_content(result["safe_reference"])
        self.assertEqual(safe["status"], "approved")
        self.assertNotIn("alice@example.com", safe["content"])
        self.assertNotIn("13800138000", safe["content"])
        self.assertNotIn("11010519491231002X", safe["content"])
        self.assertIn("联系", safe["content"])

    def test_scan_file_returns_reference_not_source_text(self):
        source = self.root / "contract.txt"
        source.write_text("邮箱 alice@example.com", encoding="utf-8")
        result = self.core.scan_file(str(source))
        self.assertEqual(result["status"], "approved")
        self.assertNotIn("alice@example.com", str(result))

    def test_txt_markdown_docx_and_text_pdf(self):
        sources = [self.root / "case.txt", self.root / "case.md"]
        for source in sources:
            source.write_text("联系 alice@example.com", encoding="utf-8")
        document = Document()
        document.add_paragraph("联系 alice@example.com")
        docx_path = self.root / "case.docx"
        document.save(docx_path)
        pdf_path = self.root / "case.pdf"
        pdf = canvas.Canvas(str(pdf_path))
        pdf.drawString(72, 760, "Contact alice@example.com")
        pdf.save()

        class EmptyRedaction:
            def upload_and_parse(self, path):
                return {"content": "", "is_scanned": True, "entities": []}

        self.core.redaction = EmptyRedaction()
        for source in (*sources, docx_path, pdf_path):
            with self.subTest(suffix=source.suffix):
                result = self.core.scan_file(str(source))
                self.assertEqual(result["status"], "approved")
                safe = self.core.get_safe_content(result["safe_reference"])
                self.assertNotIn("alice@example.com", safe["content"])

    def test_rejects_symlink_and_outside_root(self):
        source = self.root / "source.txt"
        source.write_text("safe", encoding="utf-8")
        link = self.root / "link.txt"
        link.symlink_to(source)
        with self.assertRaises(SecurityError):
            validate_source_path(link, (self.root,), 100)
        with self.assertRaises(SecurityError):
            validate_source_path("relative.txt", (self.root,), 100)

    def test_expired_reference_is_blocked(self):
        store = SafeReferenceStore(self.root / "short", ttl_seconds=-1)
        reference = store.create(safe_text="safe", output_path=None, source_digest="x", counts={})
        with self.assertRaises(ReferenceError):
            store.get(reference.token)

    def test_presidio_failure_is_fail_closed(self):
        class Broken:
            def analyze(self, text):
                from privacyguard.adapters.presidio import PresidioUnavailable
                raise PresidioUnavailable("offline")

        core = PrivacyGuard(self.settings, presidio=Broken())
        result = core.scrub_text("alice@example.com")
        self.assertEqual(result["status"], "blocked")
        self.assertNotIn("alice@example.com", str(result))

    def test_recheck_new_entity_is_added_to_original_list(self):
        class Semantic:
            def analyze(self, text):
                if "alice@example.com" not in text:
                    start = text.find("史莱克学院")
                    if start >= 0:
                        return [Finding("ORGANIZATION", start, start + 5, .8, "late")]
                return []
        self.core.semantic = Semantic()
        result = self.core.scrub_text("alice@example.com 联系史莱克学院")
        self.assertEqual(result["status"], "approved")
        self.assertEqual(result["counts"]["ORGANIZATION"], 1)
        self.assertNotIn("史莱克学院", self.core.get_safe_content(result["safe_reference"])["content"])

    def test_known_names_expand_to_all_occurrences(self):
        class Semantic:
            def analyze(self, text):
                start = text.find("唐三")
                return [Finding("PERSON", start, start + 2, .9, "first-only")] if start >= 0 else []
        self.core.semantic = Semantic()
        result = self.core.scrub_text("唐三交付，唐三复核。")
        self.assertEqual(result["counts"], {"PERSON": 2})
        safe = self.core.get_safe_content(result["safe_reference"])["content"]
        self.assertEqual(safe.count("<PERSON_001>"), 2)

    def test_malformed_docx_returns_blocked_without_source(self):
        path = self.root / "broken.docx"
        path.write_bytes(b"alice@example.com")
        result = self.core.scan_file(str(path))
        self.assertEqual(result["status"], "blocked")
        self.assertNotIn("alice@example.com", str(result))

    def test_failed_export_does_not_publish_reference(self):
        document = Document()
        document.add_paragraph("alice@example.com")
        path = self.root / "contract.docx"
        document.save(path)
        class Redaction:
            def upload_and_parse(self, path):
                return {"file_id": "fake", "content": "alice@example.com"}
            def execute_and_download(self, *args):
                raise RuntimeError("private: alice@example.com")
        self.core.redaction = Redaction()
        result = self.core.redact_file(str(path))
        self.assertEqual(result["status"], "blocked")
        self.assertIsNone(result["safe_reference"])
        self.assertNotIn("alice@example.com", str(result))
        self.assertEqual(list(self.core.store.root.iterdir()), [])

    def test_low_confidence_semantic_entity_blocks_safe_export(self):
        document = Document()
        document.add_paragraph("项目名称 星斗计划")
        path = self.root / "uncertain.docx"
        document.save(path)

        class UncertainSemantic:
            def analyze(self, text):
                start = text.find("星斗计划")
                return [Finding("PROJECT", start, start + 4, .75, "ner")] if start >= 0 else []

        self.core.semantic = UncertainSemantic()
        result = self.core.redact_file(str(path))
        self.assertEqual(result["status"], "blocked")
        self.assertIn("需要人工确认", result["reason"])
        self.assertIsNone(result["safe_reference"])

    def test_accepts_verified_upstream_entity_with_none_confidence(self):
        source = self.root / "case.pdf"
        source.write_bytes(b"placeholder")

        class Redaction:
            def upload_and_parse(self, path):
                return {
                    "content": "当事人唐三提交合同",
                    "is_scanned": False,
                    "entities": [{"type": "PERSON", "text": "唐三", "start": 3, "end": 5, "confidence": None}],
                }

        self.core.redaction = Redaction()
        result = self.core.scan_file(str(source))
        self.assertEqual(result["status"], "approved")
        safe = self.core.get_safe_content(result["safe_reference"])
        self.assertNotIn("唐三", safe["content"])
        self.assertEqual(result["counts"], {"PERSON": 1})


class ChinaIdTests(unittest.TestCase):
    def test_validates_date_and_checksum(self):
        self.assertTrue(is_valid_china_id("11010519491231002X"))
        self.assertFalse(is_valid_china_id("11010519491331002X"))
        self.assertFalse(is_valid_china_id("110105194912310021"))
        text = "真 11010519491231002X 假 11010519491331002X"
        values = [item.value for item in detect_entities(text) if item.type == "ID_NUMBER"]
        self.assertEqual(values, ["11010519491231002X"])

    def test_reference_mask_never_returns_complete_secret(self):
        token = "abcd0123456789wxyz"
        masked = mask_secret(token)
        self.assertEqual(masked, "abcd...wxyz")
        self.assertNotIn(token, masked)


if __name__ == "__main__":
    unittest.main()
