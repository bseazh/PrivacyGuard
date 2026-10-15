"""Exercise the upstream HTTP boundary without running recognition models."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from privacyguard.adapters.redaction_everything import RedactionEverythingAdapter, RedactionEverythingError


class RedactionAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.requests = []
        self.parse_status = 200
        self.ner = {"entities": [], "recognition_failed": False}
        self.adapter = RedactionEverythingAdapter("http://local.test")

    def tearDown(self):
        self.temp.cleanup()

    def handler(self, request):
        self.requests.append(request)
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
