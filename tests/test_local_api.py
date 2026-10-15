import unittest
from unittest.mock import patch

from service import local_api


class LocalApiJobTests(unittest.TestCase):
    def setUp(self):
        with local_api._jobs_lock:
            local_api._jobs.clear()

    def test_run_job_reaches_done_and_preserves_upload_name(self):
        job_id = "job-success"
        with local_api._jobs_lock:
            local_api._jobs[job_id] = {"status": "queued", "phase": "queued"}
        result = {"name": "temporary.txt", "path": "temporary", "text": "原告张伟", "entities": []}

        with patch.object(local_api, "analyze", return_value=result):
            local_api.run_job(job_id, "short.txt", b"test", ".txt")

        with local_api._jobs_lock:
            job = dict(local_api._jobs[job_id])
        self.assertEqual(job["status"], "done")
        self.assertEqual(job["phase"], "done")
        self.assertEqual(job["progress"], 100)
        self.assertEqual(job["result"]["name"], "short.txt")
        self.assertEqual(job["result"]["path"], "local-upload")

    def test_run_job_exposes_backend_failure(self):
        job_id = "job-failure"
        with local_api._jobs_lock:
            local_api._jobs[job_id] = {"status": "queued", "phase": "queued"}

        with patch.object(local_api, "analyze", side_effect=RuntimeError("fixture failure")):
            local_api.run_job(job_id, "failure.txt", b"test", ".txt")

        with local_api._jobs_lock:
            job = dict(local_api._jobs[job_id])
        self.assertEqual(job["status"], "error")
        self.assertEqual(job["phase"], "error")
        self.assertEqual(job["message"], "fixture failure")

    def test_ner_parse_failure_retries_overlapping_halves(self):
        class FakeBackend:
            last_response_valid = True
            last_response_error = None

            def recognize(self, text, _types, prompt_variant="A"):
                self.prompt_variant = prompt_variant
                self.last_response_valid = len(text) < 2000
                self.last_response_error = None if self.last_response_valid else "truncated"
                if not self.last_response_valid:
                    return []
                start = text.find("张伟")
                return [] if start < 0 else [local_api.Entity("PERSON", "张伟", start, start + 2, 0.9, "ner")]

        text = "甲" * 1400 + "张伟" + "乙" * 1400
        with patch.object(local_api, "backend", return_value=FakeBackend()):
            entities, retries, failures = local_api.recognize_with_fallback(text, ["PERSON"])
        self.assertEqual(retries, 1)
        self.assertEqual(failures, 0)
        self.assertEqual([(item.value, item.start) for item in entities], [("张伟", 1400), ("张伟", 1400)])


if __name__ == "__main__":
    unittest.main()
