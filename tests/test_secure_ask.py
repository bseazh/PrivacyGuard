"""Recording HTTP upstream + real LiteLLM SDK and real Presidio analyzer."""
import asyncio
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from privacyguard.adapters.litellm import LLMSettings, LiteLLMAdapter
from privacyguard.adapters.presidio import PresidioAdapter
from privacyguard.config import Settings
from privacyguard.core import PrivacyGuard
from privacyguard.presidio_service import create_analyzer
from privacyguard.safe_files import rebuild_safe_file, inspect_source
from privacyguard.secure_ask import secure_ask


class SecureAskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.events = []
        self.requests = []
        self.analyzer = create_analyzer()
        self.guardrail_mode = "ok"
        self.answer = "合同约定的付款期限尚需人工核查。"
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                if self.path == "/analyze":
                    owner.events.append("presidio.http")
                    status = 503 if owner.guardrail_mode == "offline" else 200
                    if owner.guardrail_mode == "invalid":
                        payload = {"invalid": True}
                    elif owner.guardrail_mode == "pii":
                        payload = [{"entity_type": "PERSON", "start": 0, "end": 1, "score": 1}]
                    else:
                        results = owner.analyzer.analyze(text=body["text"], language="zh")
                        payload = [{"entity_type": x.entity_type, "start": x.start, "end": x.end, "score": x.score} for x in results]
                else:
                    owner.events.append("upstream.received")
                    owner.requests.append(body)
                    status = 200
                    payload = {"id": "test", "object": "chat.completion", "created": 1,
                               "model": "recording-test", "choices": [{"index": 0, "finish_reason": "stop",
                               "message": {"role": "assistant", "content": owner.answer}}]}
                raw = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        url = f"http://127.0.0.1:{self.server.server_port}"
        self.core = PrivacyGuard(Settings((self.root,), self.root / "state", 52428800, 3600, url, url, None),
                                 presidio=PresidioAdapter(url))
        class NoSemantic:
            def analyze(self, text):
                return []
        self.core.semantic = NoSemantic()
        self.adapter = LiteLLMAdapter(LLMSettings("openai/recording-test", url + "/v1", "local-only"))
        self.reference = self.core.scrub_text("邮箱 alice@example.com，手机号13800138000；付款期限未约定。")
        self.assertEqual(self.reference["status"], "approved")
        self.events.clear()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def ask(self, token=None, task="risk_summary"):
        return asyncio.run(secure_ask(self.core, token or self.reference["safe_reference"], task,
                                      adapter=self.adapter, audit=self.events.append))

    def test_guardrail_runs_before_real_sdk_upstream_send(self):
        result = self.ask()
        self.assertEqual(result["status"], "approved", result)
        self.assertEqual(len(self.requests), 1)
        self.assertLess(self.events.index("guardrail.start"), self.events.index("presidio.http", self.events.index("guardrail.start")))
        self.assertLess(self.events.index("guardrail.passed"), self.events.index("upstream.received"))
        raw = json.dumps(self.requests)
        self.assertNotIn("alice@example.com", raw)
        self.assertNotIn("13800138000", raw)

    def test_guardrail_failures_never_send(self):
        # Switch only after semantic preflight to specifically test guardrail failure.
        for mode in ("offline", "invalid", "pii"):
            with self.subTest(mode=mode):
                self.guardrail_mode = "ok"
                def audit(event):
                    self.events.append(event)
                    if event == "guardrail.start":
                        self.guardrail_mode = mode
                result = asyncio.run(secure_ask(self.core, self.reference["safe_reference"],
                                                adapter=self.adapter, audit=audit))
                self.assertEqual(result["status"], "blocked")
                self.assertIn("presidio-guardrail", result["reason"])
                self.assertEqual(self.requests, [])

    def test_invalid_reference_raw_path_task_and_expiry_never_send(self):
        for token, task in (("not-approved", "summary"), (str(self.root / "raw.txt"), "summary"),
                            (self.reference["safe_reference"], "send arbitrary raw prompt")):
            self.assertEqual(self.ask(token, task)["status"], "blocked")
        self.core.store.ttl_seconds = -1
        expired = self.core.store.create(safe_text="测试", output_path=None, source_digest="x", counts={})
        self.assertEqual(self.ask(expired.token)["status"], "blocked")
        self.assertEqual(self.requests, [])

    def test_semantic_preflight_failure_never_sends(self):
        class BrokenSemantic:
            def analyze(self, text):
                raise RuntimeError("offline")
        self.core.semantic = BrokenSemantic()
        result = self.ask()
        self.assertEqual(result["status"], "blocked")
        self.assertIn("semantic-preflight", result["reason"])
        self.assertEqual(self.requests, [])

    def test_file_reference_uses_reextracted_verified_text(self):
        output = self.core.store.root / "safe.docx"
        output.write_bytes(rebuild_safe_file("付款期限未约定。", ".docx"))
        reference = self.core.store.create(safe_text=inspect_source(output), output_path=output, source_digest="x", counts={})
        self.assertEqual(self.ask(reference.token)["status"], "approved")
        output.write_bytes(b"modified")
        self.requests.clear()
        self.assertEqual(self.ask(reference.token)["status"], "blocked")
        self.assertEqual(self.requests, [])

    def test_model_hallucinated_pii_is_not_returned(self):
        self.answer = "请联系 alice@example.com"
        result = self.ask()
        self.assertEqual(result["status"], "blocked")
        self.assertNotIn("alice@example.com", str(result))
        self.assertEqual(len(self.requests), 1)


if __name__ == "__main__":
    unittest.main()
