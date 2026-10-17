"""Exercise the upstream HTTP boundary without running recognition models."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from reportlab.pdfgen import canvas

REAL_HTTPX_CLIENT = httpx.Client

from privacyguard.adapters.redaction_everything import RedactionEverythingAdapter, RedactionEverythingError


class RedactionAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.requests = []
        self.parse_status = 200
        self.ner = {"entities": [], "recognition_failed": False}
        self.ocr_boxes = [{"text": "OCR page", "x": 0.1, "y": 0.1, "width": 0.5, "height": 0.1}]
        self.adapter = RedactionEverythingAdapter("http://local.test")

    def tearDown(self):
        self.temp.cleanup()

    def handler(self, request):
        self.requests.append(request)
        if request.url.path in {"/ocr", "/structure"}:
            return httpx.Response(200, json={"boxes": self.ocr_boxes})
        if request.url.path.endswith("/upload"):
            return httpx.Response(200, json={"file_id": "fixture", "file_type": "txt"})
        if request.url.path.endswith("/parse"):
            return httpx.Response(self.parse_status, json={"content": "合同正文", "is_scanned": False})
        return httpx.Response(200, json=self.ner)

    def call(self, source):
        client = httpx.Client(transport=httpx.MockTransport(self.handler))
        with patch("privacyguard.adapters.redaction_everything.httpx.Client", return_value=client):
            return self.adapter.upload_and_parse(source)

    def test_text_aliases_are_uploaded_as_txt(self):
        for suffix in (".txt", ".md", ".markdown", ".eml"):
            source = self.root / ("input" + suffix)
            source.write_text("合同正文")
            self.assertEqual(self.call(source)["content"], "合同正文")
            self.assertIn(b'filename="privacyguard-input.txt"', self.requests[-3].content)

    def test_recognition_failure_or_invalid_response_blocks(self):
        source = self.root / "input.txt"
        source.write_text("合同正文")
        for payload in ({"entities": [], "recognition_failed": True}, {"entities": None}, []):
            self.ner = payload
            with self.assertRaises(RedactionEverythingError):
                self.call(source)

    def test_parse_error_does_not_start_recognition(self):
        source = self.root / "input.txt"
        source.write_text("合同正文")
        self.parse_status = 503
        with self.assertRaises(RedactionEverythingError):
            self.call(source)
        self.assertFalse(any(r.url.path.endswith("/ner") for r in self.requests))

    def test_encoded_and_multipart_email_block_before_upload(self):
        source = self.root / "input.eml"
        for raw in ("Content-Type: multipart/mixed; boundary=test\n\n--test--",
                    "Content-Transfer-Encoding: base64\n\nYWJj",
                    "Subject: =?utf-8?b?YWJj?=\n\nbody"):
            source.write_text(raw)
            with self.assertRaises(RedactionEverythingError):
                self.call(source)
        self.assertEqual(self.requests, [])

    def test_scanned_pdf_ocr_requires_every_page_and_runs_has_on_rebuilt_text(self):
        source = self.root / "scan.pdf"
        pdf = canvas.Canvas(str(source))
        pdf.drawString(72, 760, "image page")
        pdf.showPage()
        pdf.drawString(72, 760, "second page")
        pdf.save()
        # The parse response is scanned/empty; OCR is returned for both pages.
        self.parse_status = 200
        self.ner = {"entities": [{"type": "PERSON", "text": "OCR page", "start": 0, "end": 8, "confidence": None}], "recognition_failed": False}
        original = self.handler
        parse_calls = {"count": 0}
        def handler(request):
            if request.url.path.endswith("/parse"):
                parse_calls["count"] += 1
                if parse_calls["count"] == 1:
                    return httpx.Response(200, json={"content": "", "is_scanned": True, "page_count": 2, "pages": []})
                return httpx.Response(200, json={"content": "OCR page\n\nOCR page", "is_scanned": False, "page_count": 1, "pages": ["OCR page\n\nOCR page"]})
            return original(request)
        with patch("privacyguard.adapters.redaction_everything.httpx.Client",
                   side_effect=lambda *args, **kwargs: REAL_HTTPX_CLIENT(transport=httpx.MockTransport(handler))):
            result = self.adapter.upload_and_parse(source)
        self.assertTrue(result["ocr_complete"])
        self.assertEqual(result["page_count"], 2)
        self.assertEqual(len(result["pages"]), 2)
        self.assertEqual(result["content"], "OCR page\n\nOCR page")

    def test_scanned_pdf_with_empty_page_is_blocked(self):
        source = self.root / "scan.pdf"
        pdf = canvas.Canvas(str(source))
        pdf.drawString(72, 760, "image page")
        pdf.showPage()
        pdf.showPage()
        pdf.save()
        self.ocr_boxes = []
        parse_calls = {"count": 0}
        def handler(request):
            if request.url.path.endswith("/parse"):
                parse_calls["count"] += 1
                return httpx.Response(200, json={"content": "", "is_scanned": True, "page_count": 2, "pages": []})
            return self.handler(request)
        with patch("privacyguard.adapters.redaction_everything.httpx.Client",
                   side_effect=lambda *args, **kwargs: REAL_HTTPX_CLIENT(transport=httpx.MockTransport(handler))):
            with self.assertRaises(RedactionEverythingError):
                self.adapter.upload_and_parse(source)
