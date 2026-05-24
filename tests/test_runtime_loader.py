import unittest
from pathlib import Path

from app.config import load_runtime_config, redact_mapping, redact_secret
from app.data import load_flattened_dataset, load_runtime_samples, sanitize_runtime_sample, strip_reference_fields

FIXTURE_PATH = Path("tests/fixtures/flattened_runtime_loader_fixture.json")


class RuntimeConfigTests(unittest.TestCase):
    def test_load_runtime_config_reads_env_values(self):
        config = load_runtime_config(
            ".env",
            environ={
                "SHOPAIKEY_BASE_URL": "https://example.invalid/v1",
                "SHOPAIKEY_API_KEY": "test-super-secret-key",
                "SHOPAIKEY_MODEL": "qwen2.5-7b-instruct",
                "LLM_TEMPERATURE": "0.2",
                "LLM_MAX_TOKENS": "1234",
            },
        )
        safe_config = config.to_safe_dict()

        self.assertEqual(config.shopaikey_base_url, "https://example.invalid/v1")
        self.assertEqual(config.shopaikey_model, "qwen2.5-7b-instruct")
        self.assertEqual(config.llm_temperature, 0.2)
        self.assertEqual(config.llm_max_tokens, 1234)
        self.assertNotEqual(safe_config["SHOPAIKEY_API_KEY"], config.shopaikey_api_key)

    def test_redact_mapping_redacts_secret_like_fields(self):
        redacted = redact_mapping(
            {
                "Authorization": "Bearer super-secret",
                "SHOPAIKEY_API_KEY": "sk-test",
                "SHOPAIKEY_MODEL": "qwen2.5-7b-instruct",
            }
        )

        self.assertNotEqual(redacted["Authorization"], "Bearer super-secret")
        self.assertNotEqual(redacted["SHOPAIKEY_API_KEY"], "sk-test")
        self.assertEqual(redacted["SHOPAIKEY_MODEL"], "qwen2.5-7b-instruct")
        self.assertEqual(redact_secret(""), "<redacted>")


class RuntimeLoaderTests(unittest.TestCase):
    def test_load_runtime_samples_strip_reference_fields(self):
        evaluation_samples = load_flattened_dataset(FIXTURE_PATH)
        runtime_samples = load_runtime_samples(FIXTURE_PATH)

        self.assertEqual(evaluation_samples[0].answer, "SENTINEL_ANSWER")
        runtime_payload = runtime_samples[0].to_payload()
        self.assertNotIn("answer", runtime_payload)
        self.assertNotIn("premises-FOL", runtime_payload)
        self.assertEqual(runtime_payload["sample_id"], "record_0000_question_0000")
        self.assertEqual(runtime_payload["question"], "Is this true?")

    def test_sanitize_runtime_sample_rejects_reference_fields(self):
        raw_sample = {
            "sample_id": "record_0000_question_0001",
            "record_id": 0,
            "question_id": 1,
            "premises-NL": ["Premise 2"],
            "question": "Can this leak?",
            "answer": "SENTINEL_ANSWER",
            "explanation": "SENTINEL_EXPLANATION",
            "idx": ["SENTINEL_IDX"],
        }

        stripped = strip_reference_fields(raw_sample)
        runtime_sample = sanitize_runtime_sample(raw_sample)
        runtime_payload = runtime_sample.to_payload()

        self.assertNotIn("answer", stripped)
        self.assertNotIn("explanation", stripped)
        self.assertNotIn("idx", stripped)
        self.assertNotIn("answer", runtime_payload)
        self.assertNotIn("explanation", runtime_payload)
        self.assertNotIn("idx", runtime_payload)
        self.assertEqual(runtime_payload["question_id"], 1)


if __name__ == "__main__":
    unittest.main()
