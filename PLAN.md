# EXACT_2026 Implementation Plan

## 1. Objective

Build an explainable educational QA system for logic-based educational queries.

Runtime input:

```json
{
  "premises-NL": ["..."],
  "question": "..."
}
```

Runtime output:

```json
{
  "answer": "Yes | No | Unknown | A | B | C | D | proof-grounded short answer",
  "explanation": "Natural-language explanation generated from proof trace"
}
```

Success criteria:

- Runtime inference uses only `premises-NL` and `question`; local evaluation may carry `sample_id`, `record_id`, and `question_id` only for caching, ordering, and artifacts.
- `premises-FOL`, `answer`, `explanation`, and `idx` are reference-only and are used only in training, validation, scoring, and error analysis.
- Local evaluation caches premise ASTs by `record_id`; API runtime caches premise ASTs by normalized/hash of `premises-NL` because API requests do not include `record_id`.
- The core first milestone handles MCQ, Yes/No/Unknown, and numeric/computation questions without hardcoding dataset entities or answers; open-ended questions receive only a best-effort proof-grounded fallback when entailed facts are available.
- Explanations are generated from proof traces, not free-form LLM reasoning.
- Debug traces identify root causes at each pipeline stage and never leak `.env` secrets.
- Any LLM used for conversion, fallback, or explanation verbalization is loaded from `.env` via `SHOPAIKEY_MODEL`; the current configured model identifier is `qwen2.5-7b-instruct`, and it must remain open-source and 8B parameters or fewer.

## 2. Current Project Context

Current repository structure:

- `flow.md`: target runtime flow, async requirements, cache expectations, AST/verifier stages, debug trace requirements.
- `docs/competition.md`: competition rules, open-source <=8B LLM rule, API response expectations, explainability criteria.
- `data/raw/Logic_Based_Educational_Queries.json`: raw records with shared `premises-NL`, `premises-FOL`, multiple `questions`, `answers`, `explanation`, and `idx`.
- `data/processed/Logic_Based_Educational_Queries.flattened.json`: one sample per question.
- `scripts/flatten_dataset.py`: implemented raw-to-flattened script.
- `tests/test_flatten_dataset.py`: existing unit tests for flattening.

Observed local data:

- Checked-in raw file contains 411 records.
- Checked-in flattened file contains 808 samples across 411 distinct `record_id`s.
- Flattened sample keys are `sample_id`, `record_id`, `question_id`, `premises-NL`, `premises-FOL`, `question`, `answer`, `explanation`, `idx`.
- `docs/competition.md` states 464 records / 913 questions, so the local data appears to be a smaller or different release.

Already done:

- Raw-to-flattened transformation.
- Stable local evaluation IDs: `sample_id`, `record_id`, `question_id`.
- Preservation of reference-only fields for development and scoring.
- Existing flatten tests for normal and missing optional annotations.

Missing:

- Runtime-safe loader/sanitizer.
- Early live LLM connectivity smoke validation using `.env` model settings.
- Typed Logic AST schema with implementation-ready validation.
- Question candidate extraction.
- LLM parse-frame extractor with async retry/repair/cache behavior.
- Deterministic parse-frame-to-AST compiler.
- Premise cache abstraction that supports both local `record_id` keys and API premise-hash keys.
- Numeric layer with source provenance.
- Horn prover with explicit contraposition rule support.
- Z3-compatible routing for nested implications and non-Horn fragments.
- Concrete quantifier instantiation policy.
- Semantic fallback verifier.
- Proof trace, debug trace, explanation generation, API endpoint, evaluation/scoring/error analysis.

## 3. Target Architecture

Proposed package layout:

- `app/config`: runtime settings loaded from `.env`, including `SHOPAIKEY_BASE_URL`, `SHOPAIKEY_API_KEY`, `SHOPAIKEY_MODEL`, `LLM_TEMPERATURE`, and `LLM_MAX_TOKENS`, plus safe defaults and secret redaction.
- `app/data`: flattened dataset loader, runtime sanitizer, reference-field guards.
- `app/questions`: question classification, MCQ option parsing, candidate extraction, open-ended classification.
- `app/logic`: typed AST models, compact parse-frame models, frame-to-AST compiler, JSON Schema or Pydantic-style validation, normalization, predicate map, quantifier utilities.
- `app/llm`: ShopAIKey/OpenAI-compatible client using `SHOPAIKEY_MODEL`, prompt builders, async retry/backoff, parse-frame repair, conversion cache.
- `app/cache`: premise AST cache keys, normalized text hashing, local/API single-flight lock registry.
- `app/numeric`: numeric extraction from AST and source text, deterministic evaluator, provenance tracking.
- `app/solver`: Horn prover, contraposition rule module, quantifier instantiator, Z3 adapter, semantic fallback verifier, router.
- `app/tracing`: proof trace, debug trace, root-cause classification, safe serialization.
- `app/pipeline`: async orchestration for one API request and many local evaluation samples.
- `app/output`: answer decision, MCQ submission adapter, proof-trace explanation renderer, response formatter.
- `app/api`: proposed submission endpoint.
- `scripts`: local evaluation, scoring, error aggregation, artifact generation.

Core contracts:

- `RuntimeQuery`: contains only `premises-NL` and `question`.
- `LocalRuntimeSample`: contains `sample_id`, `record_id`, `question_id`, `premises-NL`, and `question`; it excludes reference-only fields.
- `EvaluationSample`: may include reference-only fields but must be accepted only by scoring, analysis, or training utilities.
- `PremiseCacheKey`: either `record:<record_id>` for local evaluation or `premises_hash:<hash>` for API runtime.
- `FrameParseResult`: validated compact parse frames plus model metadata, cache metadata, warnings, and repair attempts.
- `FrameCompileResult`: deterministic frame-to-AST output plus AST validation metadata and compiler warnings.
- `SolverResult`: entailment status, negated entailment status, route, proof trace, unsupported features, confidence contribution.
- `PredictionResult`: answer, explanation, optional evidence, confidence, public status.
- `DebugTrace`: full stage-level trace with sanitized metadata and root-cause category.

Training/dev versus runtime:

- Training/dev utilities may read `premises-FOL`, `answer`, `explanation`, and `idx`.
- Runtime pipeline modules must not accept or import evaluation reference fields.
- Tests must use sentinel reference values to verify that runtime inference never sees or logs reference-only data.

## 4. Data Flow

### Local Evaluation Flow

1. Read `data/processed/Logic_Based_Educational_Queries.flattened.json`.
2. Split each row into:
   - sanitized `LocalRuntimeSample` for inference;
   - reference-only metadata for scoring/error analysis.
3. Submit one async task per sanitized sample.
4. Use local premise cache key `record:<record_id>`.
5. If cache miss, acquire single-flight lock for `record:<record_id>`.
6. Extract compact parse frames from shared `premises-NL`, then compile them to premise ASTs once for that record.
7. Also store successful conversion under normalized `premises-NL` hash so duplicate premise text across records can reuse the result.
8. Extract candidates from the sample `question`.
9. Extract compact parse frames from candidate text, then compile them to claim ASTs.
10. Validate and normalize candidate ASTs against the premise predicate map.
11. Extract numeric facts from both AST and source text, preserving provenance.
12. Route candidates through Horn, contraposition, numeric/Z3, nested-implication/Z3, or semantic fallback.
13. Decide answer and confidence.
14. Render explanation from proof trace.
15. Write ordered prediction/debug artifacts sorted by `record_id`, then `question_id`.
16. Score against `answer` only in evaluation code after prediction is complete.

### API Runtime Flow

1. Accept request with only `premises-NL` and `question`.
2. Normalize `premises-NL` by trimming whitespace, preserving premise order, and joining with a stable separator.
3. Compute `premises_hash` from normalized premise text plus converter/model/prompt version.
4. Use API premise cache key `premises_hash:<hash>`.
5. If cache miss, acquire single-flight lock for that premise hash.
6. Extract premise parse frames, compile them to ASTs, and validate the ASTs.
7. Continue candidate extraction, candidate AST conversion, numeric extraction, verification, decision, and explanation exactly as in local evaluation.
8. Return public response; debug trace may be logged locally only if configured and sanitized.

### Candidate Handling

MCQ:

- Detect MCQ from option shape, not answer labels.
- Parse labeled options such as `A.`, `B.`, `C.`, `D.`.
- Convert each option into a candidate claim.
- Verify each candidate independently.
- Local evaluation may emit `Unknown` when no unique option is provable.
- Submission formatting must pass through the MCQ policy described in Section 10 if the official evaluator requires only `A/B/C/D`.

Yes/No/Unknown:

- Convert the question into one claim.
- Verify claim and explicit negation of the claim.
- Return `Yes` if claim is entailed.
- Return `No` if negation is entailed.
- Return `Unknown` if neither is entailed.
- Treat `Uncertain` as an alias of `Unknown` only at scoring/submission boundaries.

Numeric/computation:

- Extract numeric evidence from validated ASTs and source text.
- Compute deterministic derived facts before proof search.
- Insert derived numeric facts into proof trace and solver context.
- Route harder arithmetic/range/time constraints to Z3.

Open-ended:

- Open-ended handling is best-effort in the first implementation milestone, not a primary success target.
- Candidate extraction classifies open-ended questions and asks the solver for the strongest entailed facts relevant to the question focus.
- Output is a short answer synthesized only from entailed facts and proof trace.
- If no grounded fact is available, return `Unknown` with low confidence rather than free-form guessing.
- Evaluation for open-ended cases should be separated from core MCQ/Yes/No/Unknown metrics unless a reliable reference format is available.

### Prediction and Debug Artifacts

Proposed local artifact names:

- `predictions.json`: ordered public-like predictions.
- `debug_traces.jsonl`: one sanitized debug trace per sample.
- `error_summary.json`: grouped root-cause counts and representative sample IDs.

## 5. Parse Frame and Typed Logic AST Design

The LLM should not be responsible for producing full formal ASTs directly. Runtime conversion is a two-step process:

```text
natural language
  -> LLM compact parse frame
  -> frame validator
  -> deterministic frame-to-AST compiler
  -> AST validator and normalizer
```

Compact parse frames are easier for the LLM to produce and easier to repair. The deterministic compiler is responsible for adding formal quantifier structure, source metadata, normalized predicate names, numeric AST nodes, and final AST shape.

### Compact Parse Frame Schema

Use a strict JSON Schema or Pydantic-style discriminated union with `kind` as the discriminator.

Shared parse-frame fields:

- `kind`: one of `rule`, `fact`, `claim`, `compound`, `ambiguous`.
- `source_id`: stable string such as `premise_0003`, `candidate_A`, or `question`.
- `source_text`: original text being parsed.
- `premise_id`: required for premise frames.
- `candidate_label`: required for candidate frames.
- `warnings`: list of parse warnings.

Common slot types:

- `predicate`: `{type: "predicate", entity, name, polarity?}`
- `numeric_condition`: `{type: "numeric_condition", entity, attribute, op, value?, unit?, expression?}`
- `numeric_value`: `{type: "numeric_value", entity, attribute, value, unit?}`
- `arithmetic_expression`: `{type: "arithmetic_expression", op, operands}`
- `entity_relation`: `{type: "entity_relation", subject, relation, object, polarity?}`

Example rule frame:

```json
{
  "kind": "rule",
  "scope": "students",
  "if": [
    {
      "type": "numeric_condition",
      "entity": "student",
      "attribute": "cumulative_gpa",
      "op": ">=",
      "value": 7.0
    }
  ],
  "then": [
    {
      "type": "predicate",
      "entity": "student",
      "name": "allowed_change_major",
      "polarity": true
    }
  ],
  "source_id": "premise_0001",
  "source_text": "Students are allowed to change majors if their cumulative GPA is 7.0 or higher.",
  "premise_id": 1,
  "warnings": []
}
```

Example fact frame:

```json
{
  "kind": "fact",
  "entity": "Mai",
  "facts": [
    {
      "type": "numeric_value",
      "attribute": "cumulative_gpa",
      "value": 7.2
    }
  ],
  "source_id": "premise_0022",
  "source_text": "Mai has a cumulative GPA of 7.2.",
  "premise_id": 22,
  "warnings": []
}
```

Example claim frame:

```json
{
  "kind": "claim",
  "answer_type": "yes_no",
  "claim": {
    "type": "predicate",
    "entity": "Mai",
    "name": "successfully_change_major",
    "polarity": true
  },
  "source_id": "question",
  "source_text": "Can Mai successfully change majors?",
  "candidate_label": "claim",
  "warnings": []
}
```

Frame validation must check required slots, allowed enums, source metadata, numeric operator validity, and whether an ambiguous frame should be repaired before compilation.

Frame-to-AST compiler responsibilities:

- Convert `rule` frames into `forall` / `implies` AST structures.
- Convert `fact` frames into ground predicate, numeric value, or comparison ASTs.
- Convert `claim` frames into candidate ASTs with `candidate_label`.
- Convert numeric frame slots into `compare`, `arith`, `num_ref`, and number terms.
- Add source metadata to AST roots.
- Preserve implication direction and explicit polarity.
- Record compiler warnings when a frame slot cannot be safely compiled.

### Typed Logic AST Schema

Use a strict JSON Schema or Pydantic-style discriminated union with `type` as the discriminator.

### Shared Metadata Fields

Root AST nodes must include source metadata so proof traces can cite their origin. Nested child nodes should preserve source metadata when the converter can provide reliable spans.

- `source_id`: stable string such as `premise_0003`, `candidate_A`, or `question`.
- `source_text`: original text span used to create the node.
- `premise_id`: zero-based premise index for premise-derived nodes; absent for candidate-only nodes.
- `candidate_label`: `A`, `B`, `C`, `D`, `claim`, or `open` for candidate-derived nodes.
- `confidence`: optional conversion confidence in `[0.0, 1.0]`.

Required root metadata:

- Premise AST root: `source_id`, `source_text`, `premise_id`.
- Candidate AST root: `source_id`, `source_text`, `candidate_label`.
- API/runtime question-level AST root: `source_id`, `source_text`.

### Term Representation

Variables:

```json
{"kind": "var", "name": "x"}
```

Constants:

```json
{"kind": "const", "name": "sophia", "surface": "Sophia", "domain": "student"}
```

Numeric literals:

```json
{"kind": "number", "value": 8.5, "unit": "score"}
```

Rules:

- Variable names are local symbols bound by quantifiers.
- Constants are extracted from the current input text and never hardcoded from the dataset.
- Constants keep both normalized `name` and original `surface`.
- Domains are optional type hints from text or predicates.

### Node Types

`pred`:

```json
{
  "type": "pred",
  "name": "qualifies_for_scholarship",
  "args": [{"kind": "var", "name": "x"}],
  "source_id": "premise_0001"
}
```

Required fields: `type`, `name`, `args`.

Validation:

- `name` must be normalized snake_case.
- `args` must be a list of terms.
- Predicate arity must be consistent within a premise bundle and candidate bundle.

`not`:

```json
{"type": "not", "body": {"type": "pred", "name": "eligible", "args": []}}
```

Required fields: `type`, `body`.

Validation:

- `body` must be a logic node.
- `not` means explicit classical negation, not negation-as-failure.

`and` / `or`:

```json
{"type": "and", "operands": [node, node]}
```

Required fields: `type`, `operands`.

Allowed `type`: `and`, `or`.

Validation:

- `operands` must contain at least two nodes.
- Nested same connective may be flattened during normalization.

`implies`:

```json
{"type": "implies", "if": node, "then": node}
```

Required fields: `type`, `if`, `then`.

Validation:

- Both sides must be logic nodes.
- Nested implications remain nested and must preserve scope.

`forall`:

```json
{
  "type": "forall",
  "vars": [{"name": "x", "domain": "student"}],
  "body": node
}
```

Required fields: `type`, `vars`, `body`.

Validation:

- `vars` must be non-empty.
- Bound variables are visible only in `body`.

`exists`:

```json
{
  "type": "exists",
  "vars": [{"name": "x", "domain": "course"}],
  "body": node
}
```

Required fields: `type`, `vars`, `body`.

Validation:

- Existential variables must not escape their body.
- Existential claims are supported only in bounded cases described in Section 7.

`compare`:

```json
{
  "type": "compare",
  "op": ">=",
  "left": {"type": "num_ref", "name": "gpa", "args": [{"kind": "const", "name": "sophia"}]},
  "right": {"kind": "number", "value": 3.5, "unit": "gpa"}
}
```

Required fields: `type`, `op`, `left`, `right`.

Allowed `op`: `<`, `<=`, `=`, `!=`, `>=`, `>`.

`arith`:

```json
{
  "type": "arith",
  "op": "average",
  "operands": [{"kind": "number", "value": 7}, {"kind": "number", "value": 10}]
}
```

Required fields: `type`, `op`, `operands`.

Allowed arithmetic `op`: `add`, `sub`, `mul`, `div`, `percentage_of`, `average`, `weighted_average`, `date_add`, `time_add`.

`num_ref`:

```json
{"type": "num_ref", "name": "credits_completed", "args": [{"kind": "const", "name": "student"}], "unit": "credits"}
```

Required fields: `type`, `name`, `args`.

### Normalization Rules

- Normalize predicate and numeric reference names to snake_case.
- Flatten associative `and`/`or`.
- Remove double negation.
- Preserve implication direction; do not rewrite implications during normalization.
- Preserve explicit classical negation.
- Preserve all source metadata needed for proof trace citations.
- Maintain a per-premise-bundle predicate phrase map.

## 6. LLM Parse-Frame Extraction Plan

Converter strategy:

- Use the configured `.env` model only: `SHOPAIKEY_MODEL` through the `SHOPAIKEY_BASE_URL` endpoint and `SHOPAIKEY_API_KEY` credential.
- The current local configured model identifier is `qwen2.5-7b-instruct`; keep this as the runtime model unless `.env` is intentionally changed.
- Validate/document that the configured model is open-source and 8B parameters or fewer before submission.
- LLM extracts compact parse frames from natural language; it does not produce final answers and should not be responsible for constructing full formal ASTs.
- A deterministic frame-to-AST compiler converts validated frames into the strict AST schema.
- Premise frame extraction and candidate frame extraction use separate prompts.
- Prompts include generic frame examples, allowed frame kinds/slot types, metadata requirements, and instructions to return uncertainty instead of inventing entities.
- Runtime prompts must never include `premises-FOL`, `answer`, `explanation`, or `idx`.

Early live validation:

- Run an LLM connectivity smoke test as soon as `.env` config loading exists, before adding substantial downstream parsing/solver logic.
- The early smoke test must use `SHOPAIKEY_BASE_URL`, `SHOPAIKEY_API_KEY`, and `SHOPAIKEY_MODEL` from `.env`, but must never print or serialize raw secrets.
- The early smoke prompt should be tiny and runtime-safe, for example asking the model to return a minimal JSON object unrelated to dataset answers.
- The early smoke test validates authentication, model availability, timeout behavior, and basic response shape only; it does not validate parse-frame quality.
- If `.env` is missing required values or the provider/network is unavailable, report the smoke as blocked with sanitized details.
- Once the LLM parse-frame extractor exists, run a second live smoke test that requests strict compact parse-frame JSON and validates the returned frame schema.

Numeric frame extraction requirements:

- When source text contains quantities, percentages, scores, GPA, credits, semesters, deadlines, durations, fees, ranks, averages, weighted averages, thresholds, or comparison phrases, the LLM must emit numeric frame slots instead of plain predicates.
- Comparison phrases include `at least`, `higher than`, `lower than`, `no more than`, `within`, `before`, `after`, `between`, `or higher`, `or lower`, `minimum`, and `maximum`.
- Numeric facts about named entities should use `numeric_value`.
- Numeric requirements or thresholds should use `numeric_condition`.
- Computed expressions such as percentages, averages, fee penalties, weighted scores, and date/time offsets should use `arithmetic_expression`.
- Do not flatten expressions such as `75% of the standard score` into a bare number unless the value is explicitly computed by the deterministic numeric layer.
- Do not leave numeric requirements as generic predicates like `meets_exam_requirement`; represent the numeric condition explicitly and let the symbolic layer derive the predicate later if needed.

Examples:

```text
"Mai scored 78%."
-> numeric_value(attribute="exam_score", entity="Mai", value=78, unit="percent")

"Students must have a GPA of 7.0 or higher."
-> numeric_condition(attribute="gpa", entity="student", op=">=", value=7.0)

"Students must achieve at least 75% of the standard score."
-> numeric_condition(
     attribute="exam_score",
     entity="student",
     op=">=",
     expression=arithmetic_expression(
       op="percentage_of",
       operands=[
         {value: 75, unit: "percent"},
         {attribute: "standard_score"}
       ]
     )
   )

"Applications must be submitted at least 30 days before the council meeting."
-> numeric_condition(attribute="application_days_before_meeting", entity="student", op=">=", value=30, unit="days")
```

Async/batched calls:

- Local evaluation batches premise conversion by `record_id` where possible.
- API runtime batches only within the current request and cache key.
- Candidate frame extraction runs per sample after candidate extraction.
- Use semaphore-limited async calls.
- Apply per-request timeout and per-sample timeout.
- Cache parse frames by normalized source text, converter version, prompt version, and model identifier. Cache compiled ASTs separately by frame hash plus compiler version.

Retry/repair:

- First pass requests strict JSON compact parse frames.
- JSON parse/frame-schema failures trigger a repair prompt that includes only the original runtime text and validation errors.
- Transient API failures use exponential backoff with jitter.
- Deterministic frame-schema failures are repaired only through the configured repair loop.
- If frame repair fails, mark `llm_frame_error` or `frame_validation_error` and route to semantic fallback only if fallback is enabled for that case.
- If frame validation succeeds but deterministic compilation fails, mark `frame_compile_error` or `schema_validation_error`.

Confidence:

- Start from converter confidence if available.
- Penalize invalid first pass, repairs, ambiguous frames, frame compile warnings, unsupported AST nodes, predicate-map conflicts, and fallback use.
- Do not let LLM confidence override symbolic proof results.

Reference supervision:

- `premises-FOL` may be used only offline for converter evaluation, training, synthetic supervision, and error analysis.
- Offline use must be isolated from runtime code paths.
- Add tests that feed sentinel reference fields into evaluation rows and verify the converter receives none of them.

## 7. Symbolic Verification Plan

### Routing Decision

Implement concrete first-milestone routing:

- Horn-compatible facts/rules -> custom Horn prover.
- Single-literal contraposition cases -> Horn prover with explicit contraposition proof rule.
- Numeric deterministic computations -> numeric evaluator, then solver context.
- Numeric constraints and propositional/non-Horn fragments -> Z3 adapter.
- Nested implication/meta-logic -> Z3-compatible encoding only when it can be grounded to finite propositional/predicate atoms; otherwise `solver_capability_gap`.
- Low-confidence or unsupported symbolic cases -> semantic fallback verifier with lower confidence.

No natural-deduction/meta-logic module is planned for the first milestone. If Z3 cannot encode a nested implication safely after bounded grounding, the router must not guess; it must return `solver_capability_gap` and optionally invoke semantic fallback.

### Horn Prover Scope

Supported:

- Ground facts.
- Explicit negated facts as classical literals.
- Universal Horn rules after bounded instantiation.
- Conjunction antecedents.
- Unary/binary/n-ary predicates with consistent arity.
- Forward chaining plus direct goal lookup.

Unsupported:

- Disjunctive consequents.
- Existential rule consequents that require creating new unknown witnesses.
- Unbounded quantifier reasoning.
- Higher-order/meta-level variables.

### Contraposition Strategy

Contraposition is handled inside the Horn prover as a separate proof rule, not as normalization.

Safe first-milestone cases:

- Literal-to-literal implication `A -> B` may support derived rule `not B -> not A`.
- Literal-to-literal implication `not A -> not B` may support derived rule `B -> A`.
- The `not` node must represent explicit classical negation from the AST.
- Variables in the original rule must be universally bound or already grounded by bounded instantiation.
- Predicate arity and argument positions must match exactly.

Do not apply contraposition when:

- The antecedent or consequent is a conjunction, disjunction, existential, arithmetic expression, or nested implication.
- Negation is inferred only from absence of proof.
- The rule contains unsupported quantifier scope or ungrounded variables.

Proof trace:

- Contraposition must produce a trace step with rule `contraposition`, source premise IDs, original implication, derived implication, and instantiated constants/variables.

Required tests:

- `not A -> not B` plus fact `B` entails `A`.
- `A -> B` plus fact `not B` entails `not A`.
- Contraposition is not applied to `A and C -> B`.
- Contraposition is not applied when negation is only missing evidence.

### Quantifier Handling Strategy

`forall`:

- Treat universal rules as schemas.
- First attempt schema-level universal matching when both premise and candidate are generic formulas, for example proving a generic `forall x. A(x) -> B(x)` candidate from a matching universal rule without requiring a concrete constant.
- Instantiate over bounded constants discovered from current `premises-NL`, candidate text, and validated AST terms when the claim is ground or when proof search needs concrete facts.
- Domain constraints restrict instantiation when a variable has a domain.
- If no constants match a required domain and schema-level matching is not applicable, keep the rule uninstantiated and report unsupported/unused status.

`exists`:

- Existential facts in premises may create a scoped witness constant only when the witness does not need to be named in the final answer.
- Existential candidate claims are supported only when an existing grounded fact can satisfy the claim.
- Existential rules that require inventing new entities for downstream reasoning are unsupported in the first milestone.

Free variables:

- Free variables in premise ASTs are validation errors unless the converter explicitly marks them as constants.
- Free variables in candidate ASTs are interpreted as universally scoped only for generic question forms when the converter marks the candidate as `generic_claim`; otherwise validation fails.

Unsupported quantifier cases:

- Unbounded universals that cannot be matched at schema level and have no finite constant set.
- Nested alternating quantifiers such as `forall exists` where witnesses must be constructed.
- Quantification over predicates or propositions.
- Existential consequents that introduce reusable entities.

Required tests:

- Universal rule instantiates over discovered constants.
- Generic universal candidate is proven through schema-level universal matching without discovered constants.
- Domain mismatch prevents invalid instantiation.
- Existing fact satisfies bounded existential candidate.
- Unbounded or alternating quantifier pattern returns `solver_capability_gap`.

### Z3 Adapter Scope

Supported:

- Grounded Boolean atoms from predicate ASTs.
- Numeric comparisons and arithmetic expressions.
- Finite propositional encodings of non-Horn implications.
- Nested implications only after all variables are bounded and converted to finite Boolean formulas.

Unsupported:

- Unbounded first-order quantifiers.
- Higher-order predicates.
- Natural-language-only relations with no AST grounding.
- Nested implications that require proof over rule schemas instead of finite instances.

### Semantic Fallback Verifier

Purpose:

- Provide a low-confidence backup when AST conversion, routing, or solver capability fails.
- Preserve explainability by returning a trace that clearly labels fallback use.

When used:

- AST is valid enough to identify candidate text, but symbolic route is unsupported.
- LLM conversion has low confidence after repair.
- Z3/Horn returns `solver_capability_gap`.
- Numeric layer cannot safely parse a computation but candidate text remains available.

Inputs:

- Sanitized `premises-NL`.
- Candidate text/options.
- Available validated AST fragments.
- Symbolic failure reason and root-cause category.

Outputs:

- Candidate ranking or Yes/No/Unknown suggestion.
- Fallback rationale tied to premise snippets.
- Confidence capped below any successful symbolic proof.
- Debug trace with `route: semantic_fallback`.

Rules:

- Fallback must not override a strong symbolic result.
- Fallback must not use reference-only fields.
- Fallback explanation must state uncertainty when no proof trace exists.
- For MCQ, fallback can break ties only when no symbolic result is uniquely provable and the confidence cap is recorded.

Required tests:

- Symbolic proof result wins over fallback.
- Unsupported route invokes fallback with confidence penalty.
- Fallback receives no reference-only fields.
- Debug trace records the original solver gap and fallback route.

## 8. Debug Trace and Root-Cause Analysis

Debug trace schema:

- IDs: `sample_id`, `record_id`, `question_id`, and `premises_hash` when available.
- Input summary: premise count, question type, candidate count; no raw secrets.
- Cache: mode `local_record_id` or `api_premises_hash`, key redacted/hash only, cache hit, single-flight wait.
- Candidate extraction: status, candidates, warnings.
- LLM frame extraction: model identifier, prompt version, attempts, retries, timeout, repair count, cache hit.
- Frame validation and compilation: frame kind, validation errors, compiler version, compile warnings, AST validation status.
- AST validation: status, node counts, errors, warnings.
- Normalization: predicate map, arity warnings, source metadata coverage.
- Quantifier instantiation: constants discovered, instantiations made, unsupported quantifier cases.
- Numeric computation: source spans, extracted quantities, derived facts, comparisons, provenance.
- Solver: route, claim result, negated result, contraposition use, Z3 status, fallback status, unsupported features.
- Proof trace: ordered derivation steps with source IDs.
- Decision: answer, confidence, MCQ local/submission policy used.
- Root cause: category and sanitized message.
- Final status: `ok`, `failed`, or `partial`.

Root-cause categories:

- `candidate_extraction_error`
- `llm_frame_error`
- `frame_validation_error`
- `frame_compile_error`
- `schema_validation_error`
- `normalization_error`
- `quantifier_instantiation_error`
- `numeric_extraction_error`
- `solver_routing_error`
- `solver_capability_gap`
- `proof_search_error`
- `semantic_fallback_used`
- `decision_error`
- `explanation_error`
- `annotation_noise`
- `timeout_error`
- `api_error`

Safe logging:

- Never log `.env` values, API keys, auth headers, or secret-bearing URLs.
- Log model identifier and sanitized error type only.
- Prediction artifacts may include source premises because they are runtime input, but they must not include reference-only fields except in explicitly separate scoring/error-analysis artifacts.

Error aggregation:

- Compare predictions to reference answers only in scoring scripts.
- Group failures by root cause, question type, solver route, fallback use, confidence band, cache mode, and repair count.
- Include representative sample IDs for review.

## 9. Async Evaluation Plan

Execution model:

- Load `.env` once.
- Create bounded semaphore from config.
- Spawn one async task per sanitized flattened sample.
- Use `asyncio.gather(..., return_exceptions=True)` or equivalent so one failed sample does not stop the batch.
- Sort final outputs by `record_id`, then `question_id`.

Local evaluation caching:

- Primary premise cache key: `record:<record_id>`.
- Single-flight lock key: `record:<record_id>`.
- Secondary conversion cache key: `premises_hash:<hash(normalized premises-NL + converter version)>`.
- If two local records share identical premise text, the record cache may reuse the secondary conversion result while still storing a per-record bundle for traceability.

API runtime caching:

- Primary premise cache key: `premises_hash:<hash(normalized premises-NL + converter version)>`.
- Single-flight lock key: same premise hash.
- No API code should assume `record_id`, `question_id`, or `sample_id` exists.

Candidate conversion caching:

- Cache candidate parse frames by normalized candidate text, predicate-map signature, converter version, prompt version, and model identifier.
- Cache compiled candidate ASTs by frame hash, predicate-map signature, and compiler version.
- Candidate caches must preserve source metadata per sample/candidate when reused.

Retries/backoff:

- Retry transient HTTP, timeout, rate-limit, and server errors with exponential backoff and jitter.
- Do not retry deterministic frame/AST validation failures except through the configured frame repair loop.
- Max attempts, timeout, and concurrency are config values.

Failed sample handling:

- Emit a prediction with `Unknown` or a submission-adapter fallback where required.
- Emit a full debug trace with root cause.
- Continue the batch.

## 10. API Submission Plan

Endpoint contract:

- Proposed endpoint: `POST /predict`.
- Request body: `premises-NL: list[str]`, `question: str`.
- Response body: required `answer`, `explanation`; optional `fol`, `cot`, `premises`, `confidence`.

Runtime config:

- `.env` is the source of truth for the runtime model and model endpoint.
- Required model settings are `SHOPAIKEY_BASE_URL`, `SHOPAIKEY_API_KEY`, and `SHOPAIKEY_MODEL`; the current configured model identifier is `qwen2.5-7b-instruct`.
- `LLM_TEMPERATURE` and `LLM_MAX_TOKENS` configure parse-frame generation behavior.
- Additional `.env` settings may define host, port, timeout, concurrency, retry, and cache behavior.
- `.env.example` should contain non-secret placeholders.
- `.env` must not be committed, printed, or copied into artifacts.

MCQ output policy:

- Internal/local evaluation policy may return `Unknown` for MCQ when no unique option is provable.
- Official submission policy is configurable:
  - If official evaluator accepts `Unknown`, emit internal answer unchanged.
  - If official evaluator requires `A/B/C/D`, use a submission adapter that selects the highest-confidence option only after recording `decision_policy: forced_mcq_choice`; if all candidates are tied or confidence is below threshold, select the configured deterministic fallback and mark low confidence.
  - Forced-choice traces must include the original internal answer, selected fallback option, candidate scores, threshold, confidence penalty, and the reason the adapter was required.
- The submission adapter must be isolated from local scoring so local metrics can still measure true `Unknown` behavior.

Security/competition constraints:

- Runtime LLM calls must use the configured `SHOPAIKEY_MODEL`; do not silently fall back to GPT, Claude, Gemini, or another closed-source model.
- Any external data/model used for training or inference must be disclosed in the one-page solution description.
- API runtime must not depend on reference annotations.
- Malformed requests should return safe validation errors.

## 11. Testing and Validation Strategy

Required unit tests:

- Runtime sanitizer removes `premises-FOL`, `answer`, `explanation`, and `idx`.
- Local cache uses `record_id`; API cache uses normalized premise hash without `record_id`.
- Candidate extraction handles MCQ, Yes/No/Unknown, numeric, open-ended, and ambiguous option formatting.
- Parse-frame schema validates rule, fact, claim, numeric slots, required metadata, and ambiguous frames.
- Frame-to-AST compiler converts rule/fact/claim frames into validated ASTs.
- AST schema validates required fields, enum values, metadata fields, variables/constants, numeric expressions, and malformed nodes.
- Normalization preserves implication direction and source metadata.
- Contraposition derives only safe literal-to-literal cases.
- Quantifier instantiation handles supported bounded cases and rejects unsupported cases.
- Numeric layer tracks source provenance from AST and source text.
- Semantic fallback is confidence-capped and does not override symbolic results.
- Answer decision distinguishes local MCQ `Unknown` from official submission adapter output.
- Debug trace root-cause categories are stable and serialized safely.

Required integration tests:

- One sanitized sample through full mocked pipeline.
- Multiple local samples sharing `record_id` trigger one premise conversion.
- API-style repeated requests with identical `premises-NL` trigger premise-hash cache reuse.
- Retry/backoff handles mocked transient model API errors.
- Timeout produces failed/partial sample artifact without stopping the batch.
- API endpoint returns valid response from mocked pipeline.

Golden/sample tests:

- MCQ unique proof.
- MCQ no unique proof -> local `Unknown`.
- Yes, No, and Unknown cases.
- Numeric percentage/average/time comparison with provenance.
- Numeric parse frame from a record like `record_0034_question_0000` routes to numeric evaluator because frames/ASTs contain numeric slots or `compare`/`arith`/`num_ref` nodes, not because of record ID or answer label.
- `not A -> not B` contraposition.
- Nested implication encoded by Z3.
- Nested implication unsupported -> `solver_capability_gap` and fallback.
- Bounded universal instantiation.
- Schema-level universal matching without concrete constants.
- Unsupported existential/alternating quantifier.
- Best-effort open-ended proof-grounded short answer and open-ended `Unknown` fallback.

Metrics:

- Answer accuracy.
- MCQ local accuracy and submission-adapter accuracy.
- Yes/No/Unknown accuracy.
- Best-effort open-ended exact/normalized match where references allow; report separately from core metrics otherwise.
- Explanation grounding rate.
- AST validity and repair rate.
- Frame validity, frame repair, and frame compile success rate.
- Cache hit rate by local record cache and API premise-hash cache.
- Root-cause distribution.

Reference-field guard:

- Use sentinel strings in reference-only fields.
- Fail tests if sentinels appear in runtime prompts, frame extractor inputs, compiler inputs, solver inputs, explanations, debug traces, or API responses.

## 12. Implementation Batches

### Batch 1: Foundation, Config, and Runtime-Safe Data Layer

Goal: Establish project structure and prevent reference-field leakage.

Expected files/modules:

- `app/config`
- `app/data`
- `tests/test_runtime_loader.py`
- dependency manifest such as `requirements.txt` or `pyproject.toml`
- `.env.example`

Tasks:

- Create package structure.
- Define `RuntimeQuery`, `LocalRuntimeSample`, and `EvaluationSample`.
- Implement flattened loader and sanitizer.
- Add guard tests for reference-only fields.
- Capture required dependencies.

Validation commands:

- `python -m unittest tests/test_flatten_dataset.py`
- `python -m unittest tests/test_runtime_loader.py`

Completion criteria:

- Runtime samples contain only allowed runtime fields.
- Existing flatten tests still pass.
- Sentinel reference fields cannot reach runtime objects.

Risks:

- Shared evaluation objects leaking labels into inference.

### Batch 2: Cache Keys, Candidate Extraction, and Question Typing

Goal: Define cache-key behavior early and convert questions into candidate claims without using answers.

Expected files/modules:

- `app/cache`
- `app/questions`
- `tests/test_cache_keys.py`
- `tests/test_candidate_extraction.py`

Tasks:

- Implement normalized premise text hashing.
- Implement local cache key `record:<record_id>`.
- Implement API cache key `premises_hash:<hash>`.
- Implement cache key tests showing API runtime does not require `record_id`.
- Classify MCQ by option structure.
- Extract labeled options.
- Classify non-option questions as Yes/No/Unknown, numeric, or open-ended.
- Preserve original candidate text and labels.

Validation commands:

- `python -m unittest tests/test_cache_keys.py`
- `python -m unittest tests/test_candidate_extraction.py`

Completion criteria:

- Local and API cache keys are distinct and tested.
- MCQ options produce candidate lists.
- Open-ended questions are explicitly classified.

Risks:

- Treating answer labels as question type during inference.

### Batch 3: Parse Frame, Typed AST Schema, Compilation, Validation, and Normalization

Goal: Define the implementation-ready parse-frame and logic representations used downstream.

Expected files/modules:

- `app/logic/frames`
- `app/logic/compiler`
- `app/logic/ast`
- `app/logic/validation`
- `app/logic/normalization`
- `tests/test_parse_frames.py`
- `tests/test_frame_compiler.py`
- `tests/test_logic_ast.py`

Tasks:

- Implement compact parse-frame models for `rule`, `fact`, `claim`, `compound`, and `ambiguous` frames.
- Implement frame slot models for predicates, numeric conditions, numeric values, arithmetic expressions, and entity relations.
- Implement deterministic frame-to-AST compiler.
- Implement discriminated node models for `pred`, `not`, `and`, `or`, `implies`, `forall`, `exists`, `compare`, `arith`, and `num_ref`.
- Implement term models for variables, constants, and numbers.
- Validate frame required slots, AST required fields, enum values, required root metadata, variable binding, predicate arity, and numeric operands.
- Normalize predicate names and associative connectives while preserving source metadata.
- Keep nested implications as tree structures.

Validation commands:

- `python -m unittest tests/test_parse_frames.py`
- `python -m unittest tests/test_frame_compiler.py`
- `python -m unittest tests/test_logic_ast.py`

Completion criteria:

- All required parse-frame kinds validate.
- Rule/fact/claim frames compile to expected AST structures.
- All node types validate.
- Invalid scopes and malformed numeric expressions fail clearly.
- Source metadata survives normalization.

Risks:

- Frame schema too loose can let bad semantic parses compile into plausible but wrong ASTs.
- AST schema too loose for safe solver routing.

### Batch 4: Debug Trace and Proof Trace Infrastructure

Goal: Make every stage observable before adding complex reasoning.

Expected files/modules:

- `app/tracing`
- `tests/test_debug_trace.py`

Tasks:

- Add or run an early credential-gated LLM connectivity smoke check using `.env` if it has not already been recorded in `report.md`.
- Define debug trace schema.
- Define proof trace step schema.
- Add root-cause categories including quantifier, numeric, and fallback categories.
- Add safe redaction helpers.
- Add JSON/JSONL artifact writers.

Validation commands:

- early LLM connectivity smoke command using sanitized `.env` config, or a clearly reported blocked live validation.
- `python -m unittest tests/test_debug_trace.py`

Completion criteria:

- Early LLM connectivity is either validated live or reported as blocked with sanitized provider/network/config details.
- Trace serializes without secrets.
- Root-cause categories are test-covered.

Risks:

- Debug output accidentally mixing public predictions and scoring references.

### Batch 5: LLM Parse-Frame Extractor with Mockable Runtime

Goal: Extract compact parse frames from premises/candidates with retries, repair, and text-hash caching.

Expected files/modules:

- `app/llm`
- `tests/test_llm_frame_extraction.py`

Tasks:

- Define frame extractor interface.
- Implement async ShopAIKey/OpenAI-compatible HTTP client that reads `SHOPAIKEY_BASE_URL`, `SHOPAIKEY_API_KEY`, and `SHOPAIKEY_MODEL` from `.env`.
- Add strict JSON parsing and frame validation.
- Add frame repair loop.
- Add frame cache by normalized text, prompt version, extractor version, and model.
- Add mock frame extractor for tests.
- Add a required credential-gated live parse-frame smoke test when `.env` has all required model settings.

Validation commands:

- `python -m unittest tests/test_llm_frame_extraction.py`
- live parse-frame smoke command using the configured `.env` model, or a clearly reported blocked live validation.

Completion criteria:

- Mocked valid frame succeeds.
- Invalid frame triggers repair.
- Transient failures retry with backoff.
- Runtime frame extractor input excludes reference-only fields.
- Live parse-frame smoke succeeds when provider access is available, or the blocker is documented with sanitized details.

Risks:

- Provider-specific response shape changes from the configured ShopAIKey/OpenAI-compatible endpoint.

### Batch 6: Async Pipeline, Premise Cache, and Single-Flight Locks

Goal: Process local and API samples concurrently while sharing premise ASTs safely.

Expected files/modules:

- `app/pipeline`
- `scripts/evaluate_local.py`
- `tests/test_async_pipeline.py`

Tasks:

- Implement bounded async scheduler.
- Add local premise cache keyed by `record:<record_id>`.
- Add API premise cache keyed by `premises_hash:<hash>`.
- Add single-flight locks for both key modes.
- Add per-sample/request timeout and failure handling.
- Preserve local output ordering by `record_id`, `question_id`.
- Write prediction/debug artifacts.

Validation commands:

- `python -m unittest tests/test_async_pipeline.py`

Completion criteria:

- Concurrent local samples sharing a record trigger one premise conversion.
- Repeated API-style requests with same premise text trigger one premise conversion.
- Failed samples do not stop the batch.

Risks:

- Cache race conditions or record-only assumptions leaking into API runtime.

### Batch 7: Numeric Layer with Source Provenance

Goal: Extract and evaluate arithmetic/time constraints before symbolic solving.

Expected files/modules:

- `app/numeric`
- `tests/test_numeric_layer.py`

Tasks:

- Extract numeric facts from validated parse-frame numeric slots and compiled AST numeric nodes.
- Extract supplemental numeric source spans from `premises-NL`, question text, and candidate text when frames/ASTs lack enough detail.
- Link each extracted quantity to `source_id`, `source_text`, `premise_id` or `candidate_label`, and character/span metadata when available.
- Evaluate deterministic arithmetic.
- Insert derived numeric facts into solver context and proof trace.
- Route harder constraints to Z3-compatible forms.

Validation commands:

- `python -m unittest tests/test_numeric_layer.py`

Completion criteria:

- Numeric derived facts cite their source premises/candidates.
- Percentages, averages, thresholds, and time comparisons are covered.
- Numeric parse failures produce traceable warnings.

Risks:

- Source-text extraction contradicting AST extraction; AST should win when validated, and conflicts should be traced.

### Batch 8: Horn Prover, Contraposition, Quantifier Instantiation, and Entailment Decision

Goal: Support core symbolic reasoning for simple logic cases.

Expected files/modules:

- `app/solver/horn`
- `app/solver/contraposition`
- `app/solver/quantifiers`
- `app/output/decision`
- `tests/test_horn_solver.py`
- `tests/test_contraposition.py`
- `tests/test_quantifiers.py`
- `tests/test_answer_decision.py`

Tasks:

- Implement fact/rule extraction from AST.
- Implement schema-level universal matching for generic universal premise/candidate formulas.
- Instantiate universal rules over discovered constants.
- Support bounded existential candidate satisfaction.
- Add forward chaining for Horn rules.
- Add explicit safe contraposition proof rule for literal-to-literal implications.
- Check claim and negated claim.
- Implement Yes/No/Unknown and MCQ local answer selection.

Validation commands:

- `python -m unittest tests/test_horn_solver.py`
- `python -m unittest tests/test_contraposition.py`
- `python -m unittest tests/test_quantifiers.py`
- `python -m unittest tests/test_answer_decision.py`

Completion criteria:

- Safe contraposition cases pass.
- Unsafe contraposition cases are rejected.
- Supported quantifier cases instantiate correctly.
- Unsupported quantifier cases return `solver_capability_gap`.

Risks:

- Unsound contraposition if explicit negation is confused with missing evidence.

### Batch 8.5: Numeric Layer Modularization and Maintainability

Goal: Split the large Batch 7 numeric layer into focused modules after the Batch 8 solver contract is proven, while preserving exact runtime behavior.

Expected files/modules:

- `app/numeric/layer.py`
- `app/numeric/extractors.py`
- `app/numeric/resolution.py`
- `app/numeric/evaluator.py`
- `app/numeric/routing.py`
- `tests/test_numeric_layer.py`

Tasks:

- Keep `from app.numeric import build_numeric_layer` and `NumericLayerResult` stable.
- Move extraction, resolution/conflict handling, deterministic evaluation, and Z3-candidate routing into focused modules.
- Leave `app/numeric/layer.py` as thin orchestration.
- Preserve provenance, warnings, conflicts, derived facts, solver-context keys, and duplicate source-text suppression.
- Add or preserve regression tests proving no behavior drift.

Validation commands:

- `python -m unittest tests/test_numeric_layer.py`
- `python -m unittest tests/test_async_pipeline.py`
- `python -m unittest`

Completion criteria:

- Numeric module boundaries are clearer and `app/numeric/layer.py` is reduced to orchestration.
- Public numeric API and downstream solver handoff remain compatible.
- No new solver behavior, LLM calls, or dataset-specific logic is introduced.

Risks:

- Refactor drift can silently change numeric proof traces; regression tests must compare externally visible behavior.

### Batch 9: Z3 Adapter, Nested Implication Routing, and Semantic Fallback

Goal: Extend coverage to numeric/non-Horn fragments and provide a low-confidence fallback.

Expected files/modules:

- `app/solver/z3_adapter`
- `app/solver/router`
- `app/solver/semantic_fallback`
- `tests/test_solver_routing.py`
- `tests/test_z3_adapter.py`
- `tests/test_semantic_fallback.py`

Tasks:

- Detect logic fragment features.
- Route Horn-compatible cases to Horn prover.
- Encode grounded numeric/Boolean constraints in Z3.
- Encode nested implications only when fully grounded into finite Boolean formulas.
- Mark unsupported nested/meta-logic cases as `solver_capability_gap`.
- Invoke semantic fallback only when symbolic route cannot produce a strong result.
- Cap fallback confidence below successful symbolic proof confidence.

Validation commands:

- `python -m unittest tests/test_solver_routing.py`
- `python -m unittest tests/test_z3_adapter.py`
- `python -m unittest tests/test_semantic_fallback.py`

Completion criteria:

- Z3 handles supported numeric and grounded nested implication cases.
- Unsupported nested implication returns `solver_capability_gap`.
- Fallback cannot override a symbolic proof.

Risks:

- Z3 encoding becoming unsound if variables are not fully grounded.

### Batch 10: Explanation Generation, Best-Effort Open-Ended Output, and MCQ Submission Adapter

Goal: Produce concise, verifiable public outputs from proof traces.

Expected files/modules:

- `app/output/explanation`
- `app/output/format`
- `app/output/mcq_submission_adapter`
- `tests/test_explanation_output.py`
- `tests/test_open_ended_output.py`
- `tests/test_mcq_submission_adapter.py`

Tasks:

- Render explanations from proof trace steps.
- Cite premise numbers, computed values, and contraposition/Z3/fallback route when used.
- Generate best-effort first-milestone open-ended short answers only from entailed proof-trace facts.
- Add local MCQ output policy allowing `Unknown`.
- Add official submission adapter policy for evaluators that require `A/B/C/D`, including forced-choice trace details and confidence penalty.
- Include optional `fol`, `cot`, `premises`, and `confidence` fields.

Validation commands:

- `python -m unittest tests/test_explanation_output.py`
- `python -m unittest tests/test_open_ended_output.py`
- `python -m unittest tests/test_mcq_submission_adapter.py`

Completion criteria:

- Explanation references only proof trace facts.
- Open-ended answers do not invent unsupported content and return `Unknown` when no grounded fact is available.
- MCQ local/submission behavior is tested separately.

Risks:

- Submission adapter forced-choice policy can reduce explainability; trace must make this visible.

### Batch 11: API Endpoint

Goal: Expose competition-compatible prediction API.

Expected files/modules:

- `app/api`
- `tests/test_api.py`

Tasks:

- Add proposed `POST /predict`.
- Validate request shape.
- Use API premise-hash cache, not `record_id`.
- Call runtime pipeline for one query.
- Return required and optional fields.
- Redact errors and secrets.

Validation commands:

- `python -m unittest tests/test_api.py`

Completion criteria:

- Valid request returns schema-compliant response.
- Malformed request returns safe validation error.
- API path does not require local evaluation IDs or reference-only fields.

Risks:

- Endpoint details may need adjustment when final official submission spec is published.

### Batch 12: Evaluation, Scoring, and Error Analysis

Goal: Measure performance and guide improvements safely.

Expected files/modules:

- `scripts/evaluate_local.py`
- `scripts/score_predictions.py`
- `scripts/analyze_errors.py`
- `tests/test_evaluation_scripts.py`

Tasks:

- Run local evaluation over flattened data.
- Score against `answer` only outside runtime.
- Aggregate root-cause categories.
- Report accuracy by question type, solver route, fallback use, and cache mode.
- Verify no reference fields enter runtime pipeline.

Validation commands:

- `python -m unittest tests/test_evaluation_scripts.py`
- local smoke run on a small fixture dataset.

Completion criteria:

- Evaluation reads references only in scorer/analyzer.
- Error summary is grouped and actionable.

Risks:

- Scoring code leaking labels into runtime through shared objects.

### Batch 13: Regression Suite and Final Hardening

Goal: Stabilize the system for submission.

Expected files/modules:

- expanded tests and fixtures
- solution description draft
- final config/docs

Tasks:

- Add golden fixtures for MCQ, Yes, No, Unknown, numeric, contraposition, nested implication, quantifiers, fallback, and open-ended answers.
- Add timeout/rate-limit regression tests.
- Add local/API cache hit-count regression tests.
- Document the configured `.env` model choice, currently `SHOPAIKEY_MODEL=qwen2.5-7b-instruct`, and any external data usage.
- Run full test suite and local evaluation smoke test.

Validation commands:

- full unit test suite.
- local evaluation smoke run.
- API smoke test with mocked or configured model endpoint.

Completion criteria:

- All tests pass.
- Submission response shape is valid.
- Competition constraints are documented.

Risks:

- Live model latency/rate limits during final evaluation.

## 13. Risks and Mitigations

- Premise cache key mismatch: use `record_id` only for local evaluation and normalized premise hash for API runtime; test both modes.
- LLM frame parse errors: strict frame schema, repair prompts, deterministic frame-to-AST compiler, confidence penalties, fallback trace.
- Predicate mismatch: per-premise-bundle predicate map, arity checks, phrase alias tracking.
- Unsafe contraposition: implement only literal-to-literal explicit-negation cases inside the Horn prover; test unsupported cases.
- Nested implication gaps: encode only fully grounded finite formulas in Z3; otherwise return `solver_capability_gap`.
- Quantifier complexity: use bounded instantiation over discovered constants; reject unbounded or alternating quantifier patterns.
- Numeric edge cases: validated AST extraction first, source-text supplement second, provenance and conflict warnings.
- Semantic fallback overreach: cap confidence and prevent fallback from overriding symbolic proofs.
- MCQ official output mismatch: keep local `Unknown` behavior and isolate official forced-choice adapter.
- Open-ended hallucination: keep first-milestone handling best-effort, allow only proof-grounded short answers, and otherwise return `Unknown`.
- Annotation noise: treat references as scoring data, not runtime truth.
- API latency/rate limits: bounded concurrency, retries, backoff, timeouts, caching, single-flight locks.
- Overfitting: no answer/explanation/FOL access in runtime, generic prompts, sentinel tests.
- Dataset mismatch: loaders should support current 808 local samples and future official releases with the same schema.

## 14. Final Acceptance Criteria

- [ ] Runtime API accepts only `premises-NL` and `question`.
- [ ] Runtime code cannot access `premises-FOL`, `answer`, `explanation`, or `idx`.
- [ ] Local evaluation caches premise ASTs by `record_id`.
- [ ] API runtime caches premise ASTs by normalized/hash of `premises-NL`.
- [ ] Both cache modes use single-flight locks.
- [ ] Async evaluation supports bounded concurrency, retries, backoff, timeout handling, failed-sample continuation, and deterministic output ordering.
- [ ] Parse-frame schema and AST schema support required logical/numeric constructs, metadata, variables/constants, deterministic compilation, and strict validation.
- [ ] Numeric layer tracks source provenance and inserts derived facts into proof trace.
- [ ] Horn prover supports tested safe contraposition.
- [ ] Quantifier handling supports schema-level universal matching, bounded instantiation, and reports unsupported cases.
- [ ] Nested implications are routed to grounded Z3 encoding or explicit `solver_capability_gap`.
- [ ] Semantic fallback exists, is confidence-capped, and does not override symbolic proofs.
- [ ] MCQ local `Unknown` and official submission adapter behavior are tested separately.
- [ ] Best-effort open-ended first-milestone answers are proof-grounded or return `Unknown`, and are reported separately from core metrics.
- [ ] Explanations are generated from proof traces only.
- [ ] Debug traces identify root causes without leaking secrets.
- [ ] API response matches documented competition requirements as far as currently specified.
- [ ] Model configuration uses `.env` as source of truth and documents `SHOPAIKEY_MODEL`, currently `qwen2.5-7b-instruct`, as the open-source <=8B runtime model.
- [ ] Evaluation scripts score predictions only outside runtime.
- [ ] Final tests and local smoke evaluation pass.

## 15. Assumptions

- The `app/...` package layout is a proposed convention, not mandated by `flow.md` or `docs/competition.md`.
- `POST /predict` is a proposed API endpoint name based on the requirement to submit an API endpoint; the final path may change when the official schema is published.
- `requirements.txt` or `pyproject.toml` is a proposed dependency manifest convention; none currently exists in the repository.
- `.env.example` is a proposed safe configuration template; `.env` already exists locally and must remain secret.
- `predictions.json`, `debug_traces.jsonl`, and `error_summary.json` are proposed local artifact names.
- The AST validation implementation may use either JSON Schema or Pydantic-style models; the plan requires strict validation behavior, not a specific library.
- Compact parse frames are the required LLM output format for the first milestone; full AST generation by the LLM is intentionally avoided unless later evidence shows frames are insufficient.
- Z3 is the chosen first-milestone strategy for grounded nested implication/non-Horn fragments; natural-deduction/meta-logic is deferred unless later evidence shows Z3 coverage is insufficient.
- First-milestone open-ended handling is best-effort and limited to proof-grounded short answers derived from entailed facts.
- The semantic fallback may use the configured `.env` LLM or deterministic semantic scoring, but it must follow the same runtime-input and confidence-cap rules.

## 16. Open Questions / Decisions Needed
- The final official response schema is not finalized in `docs/competition.md`; currently only `answer` and `explanation` are required, with optional evidence fields encouraged.
- The model has been selected through `.env` as `SHOPAIKEY_MODEL`; before submission, verify and disclose the configured model identifier and provider in the solution description.
- It is not yet known whether the official MCQ evaluator accepts `Unknown`; the submission adapter must remain configurable until the final evaluator contract is published.
- `docs/competition.md` says the official test set will be unified across dataset types, but this repository currently contains only the Type 1 logic-based dataset; add a new adapter or pipeline extension if Type 2 specifications or files are released.
