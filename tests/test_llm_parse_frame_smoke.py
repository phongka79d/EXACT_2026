import unittest
from types import SimpleNamespace

from scripts.smoke_test_llm_parse_frame import _success_payload_from_result


class ParseFrameSmokeOutputTests(unittest.TestCase):
    def test_success_payload_includes_repair_errors_when_repair_was_used(self):
        result = SimpleNamespace(
            diagnostics={
                "model": "qwen2.5-7b-instruct",
                "endpoint": "https://example.invalid/v1/chat/completions",
                "cache_hit": False,
                "attempts": 2,
                "repair_count": 1,
                "errors": ["Fact frame must contain at least one fact slot"],
                "normalization_applied": False,
                "normalization_warnings": [],
            },
            frame=SimpleNamespace(kind="fact"),
        )

        payload = _success_payload_from_result(result)

        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["repair_count"], 1)
        self.assertEqual(payload["repair_errors"], ["Fact frame must contain at least one fact slot"])
        self.assertIn("normalization_warnings", payload)

    def test_success_payload_omits_repair_errors_when_repair_was_not_used(self):
        result = SimpleNamespace(
            diagnostics={
                "model": "qwen2.5-7b-instruct",
                "endpoint": "https://example.invalid/v1/chat/completions",
                "cache_hit": False,
                "attempts": 1,
                "repair_count": 0,
                "errors": [],
                "normalization_applied": False,
                "normalization_warnings": [],
            },
            frame=SimpleNamespace(kind="fact"),
        )

        payload = _success_payload_from_result(result)

        self.assertEqual(payload["repair_count"], 0)
        self.assertNotIn("repair_errors", payload)


if __name__ == "__main__":
    unittest.main()
