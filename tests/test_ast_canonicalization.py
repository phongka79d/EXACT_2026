import unittest

from app.logic.ast import AndNode, ConstTerm, ImpliesNode, PredNode, VarTerm
from app.logic.normalization import canonicalize_logic_bundle
from app.solver.horn import prove_entailment


def _const(name: str) -> ConstTerm:
    return ConstTerm(kind="const", name=name, surface=name.replace("_", " ").title())


def _pred(
    name: str,
    *args,
    source_id: str,
    source_text: str,
    premise_id: int | None = None,
    candidate_label: str | None = None,
) -> PredNode:
    return PredNode(
        type="pred",
        name=name,
        args=list(args),
        source_id=source_id,
        source_text=source_text,
        premise_id=premise_id,
        candidate_label=candidate_label,
    )


class AstCanonicalizationTests(unittest.TestCase):
    def test_singular_plural_entity_alignment_is_preserved_when_safe(self):
        premises = [
            _pred(
                "well_tested",
                _const("python_projects"),
                source_id="premise_1",
                source_text="Python projects are well tested.",
                premise_id=1,
            ),
            ImpliesNode(
                type="implies",
                if_node=_pred(
                    "well_tested",
                    _const("python_project"),
                    source_id="premise_2",
                    source_text="If a Python project is well tested, it is optimized.",
                    premise_id=2,
                ),
                then=_pred(
                    "optimized",
                    _const("python_project"),
                    source_id="premise_2",
                    source_text="If a Python project is well tested, it is optimized.",
                    premise_id=2,
                ),
                source_id="premise_2",
                source_text="If a Python project is well tested, it is optimized.",
                premise_id=2,
            ),
        ]
        claim = _pred(
            "optimized",
            _const("python_projects"),
            source_id="question",
            source_text="Are Python projects optimized?",
            candidate_label="claim",
        )

        canonicalized = canonicalize_logic_bundle(premises, [claim])
        result = prove_entailment(canonicalized.premise_asts, canonicalized.candidate_asts[0])
        self.assertTrue(result.entailed)
        self.assertGreaterEqual(canonicalized.entity_alias_count, 1)

    def test_relation_argument_recovery_preserves_subject_object_structure(self):
        premises = [
            _pred(
                "has",
                _const("research_methodology_course"),
                source_id="premise_0009",
                source_text="Sophia has completed the research methodology course.",
                premise_id=9,
            ),
        ]
        claim = _pred(
            "has_completed",
            _const("sophia"),
            _const("research_methodology_course"),
            source_id="question",
            source_text="Sophia has completed the research methodology course.",
            candidate_label="claim",
        )

        canonicalized = canonicalize_logic_bundle(premises, [claim])
        repaired_fact = canonicalized.premise_asts[0]
        self.assertIsInstance(repaired_fact, PredNode)
        self.assertEqual(repaired_fact.name, "has_completed")
        self.assertEqual(len(repaired_fact.args), 2)
        self.assertEqual(repaired_fact.args[0].name, "sophia")
        self.assertEqual(repaired_fact.args[1].name, "research_methodology_course")
        self.assertGreaterEqual(canonicalized.relation_repair_count, 1)

    def test_possessive_relation_object_is_recovered_for_capstone_fact(self):
        premises = [
            _pred(
                "has",
                _const("capstone_project"),
                source_id="premise_0010",
                source_text="Sophia has completed her capstone project.",
                premise_id=10,
            )
        ]
        claim = _pred(
            "has_completed",
            _const("sophia"),
            _const("capstone_project"),
            source_id="question",
            source_text="Sophia has completed a capstone project.",
            candidate_label="claim",
        )

        canonicalized = canonicalize_logic_bundle(premises, [claim])
        repaired_fact = canonicalized.premise_asts[0]
        self.assertIsInstance(repaired_fact, PredNode)
        self.assertEqual(len(repaired_fact.args), 2)
        self.assertEqual(repaired_fact.args[0].name, "sophia")
        self.assertEqual(repaired_fact.args[1].name, "capstone_project")
        self.assertGreaterEqual(canonicalized.relation_repair_count, 1)

    def test_has_completed_and_completed_forms_align_without_entity_loss(self):
        learner = _const("alex")
        premises = [
            _pred(
                "has",
                _const("research_methodology_course"),
                source_id="premise_1",
                source_text="Alex has completed the research methodology course.",
                premise_id=1,
            ),
            _pred(
                "completed",
                learner,
                _const("research_methodology"),
                source_id="premise_2",
                source_text="Alex completed research methodology.",
                premise_id=2,
            ),
        ]
        claim = _pred(
            "completed",
            learner,
            _const("research_methodology_course"),
            source_id="question",
            source_text="Alex completed the research methodology course.",
            candidate_label="claim",
        )

        canonicalized = canonicalize_logic_bundle(premises, [claim])
        recovered = canonicalized.premise_asts[0]
        direct = canonicalized.premise_asts[1]
        self.assertIsInstance(recovered, PredNode)
        self.assertIsInstance(direct, PredNode)
        self.assertEqual(recovered.name, direct.name)
        self.assertEqual(recovered.args[0].name, "alex")
        self.assertEqual(direct.args[0].name, "alex")
        self.assertEqual(recovered.args[1].name, direct.args[1].name)
        result = prove_entailment(canonicalized.premise_asts, canonicalized.candidate_asts[0])
        self.assertTrue(result.entailed)

    def test_generic_multi_step_eligibility_chain_proves_final_conclusion(self):
        alex = _const("alex")
        rule1_text = "If Alex completed core curriculum and passed science assessment, Alex is qualified for advanced courses."
        rule2_text = "If Alex is qualified and completed research methodology, Alex is eligible for the international program."
        rule3_text = "If Alex is eligible and completed capstone project, Alex is awarded honors diploma."
        rule4_text = "If Alex is awarded honors diploma and completed community service, Alex qualifies for scholarship."
        premises = [
            ImpliesNode(
                type="implies",
                if_node=AndNode(
                    type="and",
                    operands=[
                        _pred("completed", alex, _const("core_curriculum"), source_id="premise_r1", source_text=rule1_text, premise_id=1),
                        _pred("passed", alex, _const("science_assessment"), source_id="premise_r1", source_text=rule1_text, premise_id=1),
                    ],
                ),
                then=_pred("qualified_for_advanced_courses", alex, source_id="premise_r1", source_text=rule1_text, premise_id=1),
                source_id="premise_r1",
                source_text=rule1_text,
                premise_id=1,
            ),
            ImpliesNode(
                type="implies",
                if_node=AndNode(
                    type="and",
                    operands=[
                        _pred("qualified_for_advanced_courses", alex, source_id="premise_r2", source_text=rule2_text, premise_id=2),
                        _pred("completed", alex, _const("research_methodology"), source_id="premise_r2", source_text=rule2_text, premise_id=2),
                    ],
                ),
                then=_pred("eligible_for_international_program", alex, source_id="premise_r2", source_text=rule2_text, premise_id=2),
                source_id="premise_r2",
                source_text=rule2_text,
                premise_id=2,
            ),
            ImpliesNode(
                type="implies",
                if_node=AndNode(
                    type="and",
                    operands=[
                        _pred("eligible_for_international_program", alex, source_id="premise_r3", source_text=rule3_text, premise_id=3),
                        _pred("completed", alex, _const("capstone_project"), source_id="premise_r3", source_text=rule3_text, premise_id=3),
                    ],
                ),
                then=_pred("awarded_honors_diploma", alex, source_id="premise_r3", source_text=rule3_text, premise_id=3),
                source_id="premise_r3",
                source_text=rule3_text,
                premise_id=3,
            ),
            ImpliesNode(
                type="implies",
                if_node=AndNode(
                    type="and",
                    operands=[
                        _pred("awarded_honors_diploma", alex, source_id="premise_r4", source_text=rule4_text, premise_id=4),
                        _pred("completed", alex, _const("community_service"), source_id="premise_r4", source_text=rule4_text, premise_id=4),
                    ],
                ),
                then=_pred("qualifies_for_university_scholarship", alex, source_id="premise_r4", source_text=rule4_text, premise_id=4),
                source_id="premise_r4",
                source_text=rule4_text,
                premise_id=4,
            ),
            _pred("has", _const("core_curriculum"), source_id="premise_f1", source_text="Alex has completed the core curriculum.", premise_id=11),
            _pred("has", _const("science_assessment"), source_id="premise_f2", source_text="Alex has passed the science assessment.", premise_id=12),
            _pred("has", _const("research_methodology_course"), source_id="premise_f3", source_text="Alex has completed the research methodology course.", premise_id=13),
            _pred("has", _const("capstone_project"), source_id="premise_f4", source_text="Alex has completed her capstone project.", premise_id=14),
            _pred("has", _const("required_community_service_hours"), source_id="premise_f5", source_text="Alex has completed required community service hours.", premise_id=15),
        ]
        claim = _pred(
            "qualifies_for_university_scholarship",
            alex,
            source_id="question",
            source_text="Scholarship qualification claim.",
            candidate_label="claim",
        )

        canonicalized = canonicalize_logic_bundle(premises, [claim])
        result = prove_entailment(canonicalized.premise_asts, canonicalized.candidate_asts[0])
        self.assertTrue(result.entailed)

    def test_passing_exam_is_not_equivalent_to_needing_exam(self):
        premises = [
            _pred(
                "passed_language_proficiency_exam",
                _const("sophia"),
                source_id="premise_1",
                source_text="Sophia passed the language proficiency exam.",
                premise_id=1,
            ),
            ImpliesNode(
                type="implies",
                if_node=_pred(
                    "passed_language_proficiency_exam",
                    _const("sophia"),
                    source_id="premise_2",
                    source_text="If Sophia passed language proficiency exam, she is eligible for international program.",
                    premise_id=2,
                ),
                then=_pred(
                    "eligible_for_international_program",
                    _const("sophia"),
                    source_id="premise_2",
                    source_text="If Sophia passed language proficiency exam, she is eligible for international program.",
                    premise_id=2,
                ),
                source_id="premise_2",
                source_text="If Sophia passed language proficiency exam, she is eligible for international program.",
                premise_id=2,
            ),
        ]
        needs_claim = _pred(
            "needs_language_proficiency_exam_for_international_program",
            _const("sophia"),
            source_id="candidate_d",
            source_text="Sophia needs to pass the language proficiency exam to be eligible for the international program.",
            candidate_label="D",
        )

        canonicalized = canonicalize_logic_bundle(premises, [needs_claim])
        result = prove_entailment(canonicalized.premise_asts, canonicalized.candidate_asts[0])
        self.assertFalse(result.entailed)

    def test_eligible_for_program_does_not_alias_to_needs_exam(self):
        premises = [
            _pred(
                "eligible_for_international_program",
                _const("sophia"),
                source_id="premise_1",
                source_text="Sophia is eligible for the international program.",
                premise_id=1,
            )
        ]
        candidates = [
            _pred(
                "eligible_for_international_program",
                _const("sophia"),
                source_id="candidate_c",
                source_text="Sophia is eligible for the international program.",
                candidate_label="C",
            ),
            _pred(
                "needs_language_proficiency_exam_for_international_program",
                _const("sophia"),
                source_id="candidate_d",
                source_text="Sophia needs language proficiency exam for international program.",
                candidate_label="D",
            ),
        ]

        canonicalized = canonicalize_logic_bundle(premises, candidates)
        name_c = canonicalized.candidate_asts[0].name
        name_d = canonicalized.candidate_asts[1].name
        self.assertNotEqual(name_c, name_d)
        self.assertGreaterEqual(canonicalized.predicate_alias_rejected_count, 0)

    def test_awarded_diploma_does_not_entail_scholarship_without_rule_chain(self):
        premises = [
            _pred(
                "awarded_honors_diploma",
                _const("sophia"),
                source_id="premise_1",
                source_text="Sophia has been awarded an honors diploma.",
                premise_id=1,
            )
        ]
        claim = _pred(
            "qualifies_for_university_scholarship",
            _const("sophia"),
            source_id="question",
            source_text="Sophia qualifies for the university scholarship.",
            candidate_label="claim",
        )

        canonicalized = canonicalize_logic_bundle(premises, [claim])
        result = prove_entailment(canonicalized.premise_asts, canonicalized.candidate_asts[0])
        self.assertFalse(result.entailed)

    def test_mcq_candidates_do_not_both_entail_from_aliasing(self):
        student = VarTerm(kind="var", name="x")
        premises = [
            _pred(
                "passed_science_assessment",
                _const("sophia"),
                source_id="premise_1",
                source_text="Sophia passed the science assessment.",
                premise_id=1,
            ),
            ImpliesNode(
                type="implies",
                if_node=_pred(
                    "passed_language_proficiency_exam",
                    student,
                    source_id="premise_2",
                    source_text="Students who passed language proficiency exam are eligible for international program.",
                    premise_id=2,
                ),
                then=_pred(
                    "eligible_for_international_program",
                    student,
                    source_id="premise_2",
                    source_text="Students who passed language proficiency exam are eligible for international program.",
                    premise_id=2,
                ),
                source_id="premise_2",
                source_text="Students who passed language proficiency exam are eligible for international program.",
                premise_id=2,
            ),
        ]
        candidate_c = _pred(
            "eligible_for_international_program",
            _const("sophia"),
            source_id="candidate_c",
            source_text="Sophia is eligible for the international program.",
            candidate_label="C",
        )
        candidate_d = _pred(
            "needs_language_proficiency_exam_for_honors_diploma",
            _const("sophia"),
            source_id="candidate_d",
            source_text="Sophia needs to pass language proficiency exam to get an honors diploma.",
            candidate_label="D",
        )

        canonicalized = canonicalize_logic_bundle(premises, [candidate_c, candidate_d])
        result_c = prove_entailment(canonicalized.premise_asts, canonicalized.candidate_asts[0])
        result_d = prove_entailment(canonicalized.premise_asts, canonicalized.candidate_asts[1])
        self.assertFalse(result_c.entailed and result_d.entailed)

    def test_canonicalization_is_not_id_dependent(self):
        premises_a = [
            _pred(
                "well_tested",
                _const("python_projects"),
                source_id="premise_A",
                source_text="Python projects are well tested.",
                premise_id=1,
            )
        ]
        premises_b = [
            _pred(
                "well_tested",
                _const("python_projects"),
                source_id="premise_X_999",
                source_text="Python projects are well tested.",
                premise_id=999,
            )
        ]
        claim_a = _pred(
            "well_tested",
            _const("python_projects"),
            source_id="question_A",
            source_text="Are Python projects well tested?",
            candidate_label="A",
        )
        claim_b = _pred(
            "well_tested",
            _const("python_projects"),
            source_id="question_B_OPTION_D",
            source_text="Are Python projects well tested?",
            candidate_label="D",
        )

        canonical_a = canonicalize_logic_bundle(premises_a, [claim_a])
        canonical_b = canonicalize_logic_bundle(premises_b, [claim_b])
        self.assertEqual(canonical_a.premise_asts[0].name, canonical_b.premise_asts[0].name)
        self.assertEqual(canonical_a.candidate_asts[0].name, canonical_b.candidate_asts[0].name)


if __name__ == "__main__":
    unittest.main()
