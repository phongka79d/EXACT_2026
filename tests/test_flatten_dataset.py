import unittest

from scripts.flatten_dataset import flatten_records


class FlattenDatasetTests(unittest.TestCase):
    def test_flattens_each_question_into_one_sample(self):
        records = [
            {
                "idx": [[1], [2, 3]],
                "premises-NL": ["Premise one.", "Premise two."],
                "premises-FOL": ["P1", "P2"],
                "questions": ["Question 1?", "Question 2?"],
                "answers": ["Yes", "A"],
                "explanation": ["Because 1.", "Because 2."],
            }
        ]

        flattened = flatten_records(records)

        self.assertEqual(len(flattened), 2)
        self.assertEqual(flattened[0]["sample_id"], "record_0000_question_0000")
        self.assertEqual(flattened[0]["record_id"], 0)
        self.assertEqual(flattened[0]["question_id"], 0)
        self.assertEqual(flattened[0]["premises-NL"], ["Premise one.", "Premise two."])
        self.assertEqual(flattened[0]["question"], "Question 1?")
        self.assertEqual(flattened[0]["answer"], "Yes")
        self.assertEqual(flattened[0]["explanation"], "Because 1.")
        self.assertEqual(flattened[0]["idx"], [1])

        self.assertEqual(flattened[1]["sample_id"], "record_0000_question_0001")
        self.assertEqual(flattened[1]["question"], "Question 2?")
        self.assertEqual(flattened[1]["answer"], "A")
        self.assertEqual(flattened[1]["explanation"], "Because 2.")
        self.assertEqual(flattened[1]["idx"], [2, 3])

    def test_missing_optional_annotations_are_none(self):
        records = [
            {
                "premises-NL": ["Premise one."],
                "questions": ["Question 1?"],
            }
        ]

        flattened = flatten_records(records)

        self.assertEqual(flattened[0]["answer"], None)
        self.assertEqual(flattened[0]["explanation"], None)
        self.assertEqual(flattened[0]["idx"], None)
        self.assertEqual(flattened[0]["premises-FOL"], None)


if __name__ == "__main__":
    unittest.main()
