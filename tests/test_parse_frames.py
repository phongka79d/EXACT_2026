import unittest

from app.logic.frames import parse_frame
from app.logic.validation import validate_parse_frame


class ParseFrameValidationTests(unittest.TestCase):
    def test_all_required_frame_kinds_validate(self):
        frames = [
            parse_frame(
                {
                    "kind": "rule",
                    "scope": "students",
                    "if": [
                        {
                            "type": "numeric_condition",
                            "entity": "student",
                            "attribute": "cumulative_gpa",
                            "op": ">=",
                            "value": 7.0,
                        }
                    ],
                    "then": [{"type": "predicate", "entity": "student", "name": "allowed_change_major"}],
                    "source_id": "premise_0001",
                    "source_text": "Students are allowed to change majors if their cumulative GPA is 7.0 or higher.",
                    "premise_id": 1,
                    "warnings": [],
                }
            ),
            parse_frame(
                {
                    "kind": "fact",
                    "entity": "Mai",
                    "facts": [{"type": "numeric_value", "attribute": "cumulative_gpa", "value": 7.2}],
                    "source_id": "premise_0002",
                    "source_text": "Mai has a cumulative GPA of 7.2.",
                    "premise_id": 2,
                    "warnings": [],
                }
            ),
            parse_frame(
                {
                    "kind": "claim",
                    "answer_type": "yes_no_unknown",
                    "claim": {"type": "predicate", "entity": "Mai", "name": "allowed_change_major"},
                    "source_id": "question",
                    "source_text": "Can Mai change majors?",
                    "candidate_label": "claim",
                    "warnings": [],
                }
            ),
            parse_frame(
                {
                    "kind": "compound",
                    "operator": "and",
                    "parts": [
                        {"type": "predicate", "entity": "Mai", "name": "has_enough_credits"},
                        {"type": "predicate", "entity": "Mai", "name": "has_minimum_gpa"},
                    ],
                    "source_id": "premise_0003",
                    "source_text": "Mai has enough credits and minimum GPA.",
                    "premise_id": 3,
                    "warnings": [],
                }
            ),
            parse_frame(
                {
                    "kind": "ambiguous",
                    "reason": "Text contains unresolved pronouns.",
                    "source_id": "question",
                    "source_text": "Did they pass?",
                    "warnings": ["Could not resolve antecedent for `they`."],
                    "options": ["entity_a", "entity_b"],
                    "candidate_label": "claim",
                }
            ),
        ]

        for frame in frames:
            validate_parse_frame(frame)

    def test_invalid_scope_fails_clearly(self):
        frame = parse_frame(
            {
                "kind": "rule",
                "scope": "123students",
                "if": [{"type": "predicate", "entity": "student", "name": "eligible"}],
                "then": [{"type": "predicate", "entity": "student", "name": "can_graduate"}],
                "source_id": "premise_0004",
                "source_text": "If eligible, students can graduate.",
                "premise_id": 4,
                "warnings": [],
            }
        )

        with self.assertRaisesRegex(ValueError, "Invalid rule scope"):
            validate_parse_frame(frame)

    def test_invalid_numeric_operator_fails_clearly(self):
        frame = parse_frame(
            {
                "kind": "rule",
                "scope": "students",
                "if": [
                    {
                        "type": "numeric_condition",
                        "entity": "student",
                        "attribute": "gpa",
                        "op": "~=",
                        "value": 7.0,
                    }
                ],
                "then": [{"type": "predicate", "entity": "student", "name": "eligible"}],
                "source_id": "premise_0005",
                "source_text": "Students with GPA ~= 7.0 are eligible.",
                "premise_id": 5,
                "warnings": [],
            }
        )

        with self.assertRaisesRegex(ValueError, "Unsupported numeric operator"):
            validate_parse_frame(frame)

    def test_malformed_arithmetic_expression_fails_clearly(self):
        frame = parse_frame(
            {
                "kind": "rule",
                "scope": "students",
                "if": [
                    {
                        "type": "numeric_condition",
                        "entity": "student",
                        "attribute": "exam_score",
                        "op": ">=",
                        "expression": {
                            "type": "arithmetic_expression",
                            "op": "percentage_of",
                            "operands": [75],
                        },
                    }
                ],
                "then": [{"type": "predicate", "entity": "student", "name": "eligible"}],
                "source_id": "premise_0006",
                "source_text": "Students must score at least 75% of the standard score.",
                "premise_id": 6,
                "warnings": [],
            }
        )

        with self.assertRaisesRegex(ValueError, "at least two operands"):
            validate_parse_frame(frame)

    def test_entity_relation_with_complement_validates(self):
        frame = parse_frame(
            {
                "kind": "fact",
                "facts": [
                    {
                        "type": "entity_relation",
                        "subject": "Mai",
                        "relation": "qualified_for",
                        "object": "scholarship",
                        "complement": "merit",
                    }
                ],
                "source_id": "premise_0007",
                "source_text": "Mai is qualified for merit scholarship.",
                "premise_id": 7,
                "warnings": [],
            }
        )
        validate_parse_frame(frame)


if __name__ == "__main__":
    unittest.main()
