from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerRegistry
from presidio_analyzer.nlp_engine import NoOpNlpEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig


def create_analyzer() -> AnalyzerEngine:
    nlp = NoOpNlpEngine(models=[{"lang_code": "zh", "model_name": "no_op"}])
    registry = RecognizerRegistry(supported_languages=["zh"])
    registry.add_recognizer(PatternRecognizer(
        supported_entity="EMAIL_ADDRESS",
        supported_language="zh",
        patterns=[Pattern("email", r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![A-Za-z0-9.-])", 0.9)],
    ))
    registry.add_recognizer(PatternRecognizer(
        supported_entity="PHONE_NUMBER",
        supported_language="zh",
        patterns=[Pattern("cn-mobile", r"(?<![0-9])1[3-9][0-9]{9}(?![0-9])", 0.9)],
    ))
    return AnalyzerEngine(registry=registry, nlp_engine=nlp, supported_languages=["zh"])


ANALYZER = create_analyzer()
ANONYMIZER = AnonymizerEngine()


class Handler(BaseHTTPRequestHandler):
    server_version = "PrivacyGuard-Presidio/0.2"

    def log_message(self, format: str, *args) -> None:
        # Never log request bodies because they can contain PII.
        return

    def send_json(self, status: int, payload: object) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_json(200, {"ok": True, "engine": "presidio", "language": "zh"})
        else:
            self.send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 4_000_000:
                raise ValueError("invalid content length")
            body = json.loads(self.rfile.read(length))
            if self.path == "/analyze":
                text = body.get("text")
                if not isinstance(text, str) or not text:
                    raise ValueError("text is required")
                results = ANALYZER.analyze(
                    text=text,
                    language=str(body.get("language", "zh")),
                    score_threshold=float(body.get("score_threshold", 0.5)),
                )
                self.send_json(200, [{"entity_type": item.entity_type, "start": item.start, "end": item.end, "score": item.score} for item in results])
            elif self.path == "/anonymize":
                text = body.get("text")
                if not isinstance(text, str):
                    raise ValueError("text is required")
                results = ANALYZER.analyze(text=text, language="zh")
                output = ANONYMIZER.anonymize(text=text, analyzer_results=results, operators={"DEFAULT": OperatorConfig("replace", {"new_value": "<REDACTED>"})})
                self.send_json(200, {"text": output.text, "items": len(output.items)})
            else:
                self.send_json(404, {"error": "not found"})
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.send_json(400, {"error": str(exc)})
        except Exception:
            self.send_json(500, {"error": "internal service error"})


def main() -> None:
    port = int(os.getenv("PRIVACYGUARD_PRESIDIO_PORT", "5002"))
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
