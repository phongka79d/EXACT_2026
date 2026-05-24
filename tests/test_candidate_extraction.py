import unittest

from app.questions import classify_question, extract_candidates


class CandidateExtractionTests(unittest.TestCase):
    def test_extracts_mcq_candidates_from_labeled_options(self):
        question = (
            "Based on the premises, what can we conclude?\n"
            "A. The curriculum improves engagement.\n"
            "B. The curriculum improves critical thinking.\n"
            "C. The curriculum needs more resources.\n"
            "D. None of the above."
        )

        result = extract_candidates(question)

        self.assertEqual(result.question_type, "mcq")
        self.assertEqual([candidate.label for candidate in result.candidates], ["A", "B", "C", "D"])
        self.assertEqual(result.candidates[0].source_id, "candidate_A")
        self.assertEqual(result.candidates[0].source_text, "The curriculum improves engagement.")
        self.assertEqual(result.candidates[1].question_type, "mcq")

    def test_classifies_yes_no_unknown_question(self):
        result = extract_candidates("Can Mai change majors this semester?")

        self.assertEqual(result.question_type, "yes_no_unknown")
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidates[0].label, "claim")
        self.assertEqual(result.candidates[0].source_id, "question")

    def test_classifies_numeric_question(self):
        result = extract_candidates("What is 75% of the standard score?")

        self.assertEqual(result.question_type, "numeric")
        self.assertEqual(result.candidates[0].label, "claim")

    def test_classifies_open_ended_question(self):
        result = extract_candidates("Why does the policy make Mai ineligible?")

        self.assertEqual(result.question_type, "open_ended")
        self.assertEqual(result.candidates[0].label, "open")

    def test_malformed_option_labels_are_ambiguous(self):
        question = (
            "Choose the correct option:\n"
            "A. Option one.\n"
            "A. Duplicate label.\n"
            "C. Option three."
        )

        result = extract_candidates(question)

        self.assertEqual(result.question_type, "ambiguous")
        self.assertEqual([candidate.label for candidate in result.candidates], ["A", "A", "C"])
        self.assertTrue(result.warnings)

    def test_mixed_question_style_prefers_option_structure(self):
        question = "Can Mai graduate?\nA. Yes\nB. No"
        result = extract_candidates(question)

        self.assertEqual(classify_question(question), "mcq")
        self.assertEqual(result.question_type, "mcq")
        self.assertEqual([candidate.label for candidate in result.candidates], ["A", "B"])


if __name__ == "__main__":
    unittest.main()

