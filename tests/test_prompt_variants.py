import unittest

from service.mlx_ner import Qwen3NerBackend, conservative_filter
from privacyguard.semantic import verified_findings


class PromptVariantTests(unittest.TestCase):
    def test_conservative_filter_removes_titles_and_generic_projects(self):
        from service.redaction_core import Entity
        kept, filtered = conservative_filter([
            Entity("PERSON", "女1", 0, 2, .9, "ner"),
            Entity("PERSON", "周总", 3, 5, .9, "ner"),
            Entity("PROJECT", "补充协议", 6, 10, .9, "ner"),
            Entity("PERSON", "张伟", 11, 13, .9, "ner"),
        ])
        self.assertEqual(filtered, 3)
        self.assertEqual([item.value for item in kept], ["张伟"])

    def test_variant_b_adds_conservative_rules_without_changing_type_set(self):
        backend = object.__new__(Qwen3NerBackend)
        backend.tokenizer = type("Tokenizer", (), {"apply_chat_template": lambda self, messages, **kwargs: messages[0]["content"]})()
        backend.model = None
        captured = {}

        def fake_generate(*args, **kwargs):
            captured["prompt"] = args[2]
            class Response:
                text = "{}"
            yield Response()

        import service.mlx_ner as module
        original = module.stream_generate
        module.stream_generate = fake_generate
        try:
            backend.last_response_valid = True
            backend.last_response_error = None
            backend.last_filtered_count = 0
            backend.recognize("文本", ["PERSON", "PROJECT"], prompt_variant="B")
            self.assertIn("男1、女1", captured["prompt"])
            self.assertIn("补充协议", captured["prompt"])
        finally:
            module.stream_generate = original

    def test_generic_project_words_are_not_semantic_entities(self):
        findings = verified_findings("用于测试的合作协议", [
            {"type": "PROJECT", "text": "测试", "start": 2, "end": 4, "confidence": .9},
            {"type": "PROJECT", "text": "合作协议", "start": 5, "end": 9, "confidence": .9},
        ], "mlx")
        self.assertEqual(findings, [])

    def test_named_project_is_retained(self):
        findings = verified_findings("星斗计划项目", [
            {"type": "PROJECT", "text": "星斗计划", "start": 0, "end": 4, "confidence": .9},
        ], "mlx")
        self.assertEqual([(item.entity_type, item.start, item.end) for item in findings], [("PROJECT", 0, 4)])


if __name__ == "__main__":
    unittest.main()
