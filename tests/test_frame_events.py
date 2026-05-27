import json
import unittest
from pathlib import Path

from app.logic.compiler import compile_frame_payload_with_events


class FrameEventLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.events_path = Path("artifacts/test_frame_events.jsonl")
        if self.events_path.exists():
            self.events_path.unlink()

    def tearDown(self):
        if self.events_path.exists():
            self.events_path.unlink()

    def test_successful_compile_emits_normalized_validated_and_compiled_events(self):
        payload = {
            "kind": "rule",
            "scope": "students",
            "if": [{"type": "predicate", "entity": "student", "name": "eligible"}],
            "then": [{"type": "predicate", "entity": "student", "name": "can_graduate"}],
            "source_id": "premise_0001",
            "source_text": "If eligible then can graduate.",
            "premise_id": 1,
            "warnings": [],
        }

        compile_frame_payload_with_events(payload, events_path=self.events_path)

        events = [json.loads(line) for line in self.events_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([event["event"] for event in events], ["normalized_frame", "validated_frame", "compiled_ast"])

    def test_rejected_event_is_emitted_on_compile_error(self):
        payload = {
            "kind": "ambiguous",
            "reason": "unclear",
            "source_id": "question",
            "source_text": "Could this be true?",
            "warnings": [],
            "options": ["x", "y"],
        }

        with self.assertRaisesRegex(ValueError, "cannot be compiled"):
            compile_frame_payload_with_events(payload, events_path=self.events_path)

        events = [json.loads(line) for line in self.events_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([event["event"] for event in events], ["normalized_frame", "validated_frame", "rejected"])


if __name__ == "__main__":
    unittest.main()
