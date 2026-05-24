import unittest

from app.cache import (
    build_api_premise_cache_key,
    build_local_premise_cache_key,
    hash_premises_text,
    normalize_premises_text,
)


class CacheKeyTests(unittest.TestCase):
    def test_normalize_premises_preserves_order(self):
        normalized = normalize_premises_text(["  Premise one. ", "Premise two."])
        self.assertEqual(normalized, "Premise one.\n<PREMISE_SEP>\nPremise two.")

    def test_hash_changes_when_premise_order_changes(self):
        hash_forward = hash_premises_text(["A implies B", "B implies C"])
        hash_reverse = hash_premises_text(["B implies C", "A implies B"])
        self.assertNotEqual(hash_forward, hash_reverse)

    def test_local_cache_key_uses_record_id(self):
        self.assertEqual(build_local_premise_cache_key(42), "record:42")

    def test_api_cache_key_uses_premises_hash_without_record_id(self):
        key = build_api_premise_cache_key(["Premise one", "Premise two"])
        self.assertTrue(key.startswith("premises_hash:"))
        self.assertNotIn("record:", key)

    def test_api_cache_key_changes_with_hash_component_versioning(self):
        key_v1 = build_api_premise_cache_key(
            ["Premise one"],
            hash_components=("model=qwen2.5-7b-instruct", "prompt=v1"),
        )
        key_v2 = build_api_premise_cache_key(
            ["Premise one"],
            hash_components=("model=qwen2.5-7b-instruct", "prompt=v2"),
        )
        self.assertNotEqual(key_v1, key_v2)


if __name__ == "__main__":
    unittest.main()

