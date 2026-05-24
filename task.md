# EXACT_2026 Execution Plan

## Purpose

This document is the batch execution contract for future AI execution agents. It translates the approved direction in `flow.md` and `PLAN.md` into concrete implementation batches.

Future agents must execute one batch at a time, preserve the architecture in the source documents, validate honestly, update checklists only for completed work, and write detailed completion notes into the shared `report.md`.

## Authoritative Architecture Summary

Authoritative sources, in priority order:

1. `PLAN.md`
2. `flow.md`
3. `docs/competition.md`

Mandatory runtime path:

```text
runtime input: premises-NL + question
-> runtime-safe loader/sanitizer
-> async sample/request worker
-> premise parse-frame extraction/cache
-> frame validation
-> deterministic frame-to-AST compiler
-> candidate extraction
-> candidate parse-frame extraction/cache
-> candidate frame-to-AST compilation
-> AST validation and normalization
-> numeric extraction and feature routing
-> Horn / contraposition / bounded quantifier / Z3 / semantic fallback verifier
-> answer decision
-> proof-trace explanation
-> public output: answer + explanation + optional evidence
```

Runtime must never depend on `premises-FOL`, `answer`, `explanation`, or `idx`. Those fields are reference-only and may be used only by offline scoring, training, synthetic supervision, validation, and error analysis.

The LLM is the semantic parser, not the solver. It must emit compact parse frames. Production/runtime LLM calls must use `.env` as source of truth, especially `SHOPAIKEY_BASE_URL`, `SHOPAIKEY_API_KEY`, `SHOPAIKEY_MODEL`, `LLM_TEMPERATURE`, and `LLM_MAX_TOKENS`. The current configured runtime model identifier is `qwen2.5-7b-instruct`.

## Global Implementation Rules

- NO DATA OVERFITTING. Do not tune logic to specific record IDs, question IDs, answer labels, dataset row order, gold explanations, or gold FOL strings.
- NO HARDCODING answers, entities, predicates, or values from the dataset to improve scores. Constants must be extracted from current input text or validated parse frames only.
- Runtime inference must accept only `premises-NL` and `question`; local IDs are allowed only for caching, ordering, and artifacts.
- Reference-only fields must be blocked from runtime prompts, frame extractor inputs, compiler inputs, solver inputs, explanations, debug traces, API responses, and public predictions.
- Use compact parse frames as the first LLM output format. Do not ask the LLM to produce final answers or full formal ASTs in the main runtime path.
- Deterministic code owns schema validation, frame-to-AST compilation, numeric evaluation, symbolic verification, answer decision, and proof-trace explanation rendering.
- Numeric routing must come from parse-frame/AST numeric slots such as `numeric_condition`, `numeric_value`, `arithmetic_expression`, `compare`, `arith`, and `num_ref`, not from record ID or answer labels.
- Use `.env` model config. Do not silently fall back to GPT, Claude, Gemini, or another closed-source model.
- Never print, log, commit, copy, or write raw `.env` secrets into debug traces, predictions, tests, docs, or `report.md`.
- Async code must use bounded concurrency, retries with backoff/jitter for transient failures, timeouts, failed-sample isolation, deterministic output ordering, and single-flight locks for shared premise conversions.
- Debug traces must be structured enough to identify root cause by pipeline stage.
- Explanation text must be generated from proof traces, not free-form LLM reasoning.
- If any touched file exceeds 200 lines, the execution agent must report that file path, line count, and reason in `report.md`. If the file can be split cleanly without architecture drift, split it; otherwise keep it and document why.
- If a small defect is discovered inside the current batch scope, fix it and document it under `Minor Issues Fixed During Execution` in `report.md`.
- Do not perform unrelated cleanup, broad refactors, dependency swaps, or architecture changes outside the current batch.
- Run required validations for the batch. If live API credentials or services block validation, keep the production path implemented, run mocked tests, and report the live validation blocker honestly.

## Batch Map / Milestone Map

### Milestones

- M1 - Runtime-Safe Foundation
  - Batch 1 complete. Config, flattened loading, and reference-field isolation exist.
- M2 - Query Contract
  - Batch 2 complete. Cache keys and candidate extraction are defined without answer leakage.
- M3 - Logic Representation Contract
  - Batch 3 complete. Parse frames, AST schema, compiler, validation, and normalization are stable.
- M4 - Observability Foundation
  - Batch 4 complete. Proof/debug trace infrastructure exists before complex reasoning.
- M5 - LLM Semantic Parser
  - Batch 5 complete. Runtime can extract compact parse frames through a mockable configured LLM client.
- M6 - Async Runtime Skeleton
  - Batch 6 complete. Local/API pipeline orchestration, premise cache, and single-flight behavior work.
- M7 - Numeric Reasoning Layer
  - Batch 7 complete. Numeric evidence and derived facts are extracted with provenance.
- M8 - Core Symbolic Reasoning
  - Batch 8 complete. Horn, safe contraposition, bounded quantifiers, and answer decision work.
- M9 - Extended Verification
  - Batch 9 complete. Z3 routing and confidence-capped fallback cover supported harder fragments.
- M10 - Public Output Layer
  - Batch 10 complete. Proof-trace explanations, open-ended fallback, and MCQ submission adapter work.
- M11 - Submission API
  - Batch 11 complete. A competition-compatible prediction endpoint exists.
- M12 - Evaluation Loop
  - Batch 12 complete. Local evaluation, scoring, and error analysis are separated from runtime.
- M13 - Final Hardening
  - Batch 13 complete. Regression coverage, docs, and smoke validation are ready.

### Batch Sequence

1. Batch 1 -> Batch 2
2. Batch 2 -> Batch 3
3. Batch 3 -> Batch 4
4. Batch 4 -> Batch 5
5. Batch 5 -> Batch 6
6. Batch 6 -> Batch 7
7. Batch 7 -> Batch 8
8. Batch 8 -> Batch 9
9. Batch 9 -> Batch 10
10. Batch 10 -> Batch 11
11. Batch 11 -> Batch 12
12. Batch 12 -> Batch 13

## Mandatory Batch 1 - Foundation, Config, and Runtime-Safe Data Layer

### Goal

Establish project configuration, runtime-safe data loading, and hard separation between runtime inputs and reference-only annotations.

### Why this batch exists

All later batches depend on a safe data boundary. If reference fields can reach runtime objects, later solver and LLM accuracy can become overfit or label-leaky.

### Inputs / Dependencies

- `flow.md`
- `PLAN.md`
- `docs/competition.md`
- `data/processed/Logic_Based_Educational_Queries.flattened.json`
- Existing `scripts/flatten_dataset.py`
- Existing `tests/test_flatten_dataset.py`
- Existing `.env` with model config

### Exact Task List

- B1-T1: Create the proposed `app` package foundation without implementing later solver logic.
- B1-T2: Implement config loading that reads `.env` values, including `SHOPAIKEY_BASE_URL`, `SHOPAIKEY_API_KEY`, `SHOPAIKEY_MODEL`, `LLM_TEMPERATURE`, and `LLM_MAX_TOKENS`.
- B1-T3: Add secret redaction helpers so API keys and auth headers cannot be serialized into logs, debug traces, reports, or errors.
- B1-T4: Implement flattened dataset loading for local evaluation.
- B1-T5: Implement runtime-safe sample models: `RuntimeQuery`, `LocalRuntimeSample`, and `EvaluationSample`.
- B1-T6: Implement a sanitizer that strips `premises-FOL`, `answer`, `explanation`, and `idx` before inference.
- B1-T7: Add sentinel tests proving reference-only fields cannot reach runtime objects.
- B1-T8: Update or add dependency metadata only if needed for this batch.
- B1-T9: Record completion details, touched files, validations, and any file over 200 lines in `report.md`.

### Files or Modules Likely Created or Updated

- `app/__init__.py`
- `app/config/`
- `app/data/`
- `tests/test_runtime_loader.py`
- Existing dependency manifest if introduced or updated
- `report.md`

### Required Outputs / Artifacts

- Runtime-safe data models.
- Config loader with safe secret redaction.
- Loader for flattened dataset.
- Sanitizer that removes reference-only fields.
- Tests for loader/sanitizer behavior.
- `report.md` entry for Batch 1.

### Acceptance Criteria

- Runtime inference objects contain only allowed fields.
- `.env` model configuration is read without leaking secret values.
- Sentinel reference values fail tests if they appear in runtime objects.
- Existing flatten tests still pass.
- No solver, LLM extraction, or API endpoint is implemented in this batch.

### Required Tests or Validations

- `python -m unittest tests/test_flatten_dataset.py`
- `python -m unittest tests/test_runtime_loader.py`
- Any config/redaction tests added in this batch.

### Explicit Non-Goals

- Do not implement parse frames, ASTs, solver logic, numeric logic, API endpoint, or evaluation scoring.
- Do not call the live LLM API.
- Do not use reference fields to improve runtime predictions.

### Completion Checklist

- [x] Config loader exists and redacts secrets.
- [x] Runtime-safe data models exist.
- [x] Reference-only fields are stripped before inference.
- [x] Sentinel leakage tests pass.
- [x] `report.md` contains Batch 1 result.

## Mandatory Batch 2 - Cache Keys, Candidate Extraction, and Question Typing

### Goal

Define premise cache-key behavior and convert questions into candidate claims without using answers.

### Why this batch exists

The runtime must know what it is trying to verify before LLM parsing and solving. Cache-key behavior must be established early because local evaluation has `record_id`, while API runtime does not.

### Inputs / Dependencies

- Batch 1 outputs.
- `flow.md` sections on async execution/cache modes and candidate extraction.
- `PLAN.md` sections 4 and 12 Batch 2.

### Exact Task List

- B2-T1: Implement normalized premise text hashing that preserves premise order.
- B2-T2: Implement local premise cache key format `record:<record_id>`.
- B2-T3: Implement API premise cache key format `premises_hash:<hash>`.
- B2-T4: Add tests proving API cache keys do not require `record_id`.
- B2-T5: Implement MCQ detection from option structure, not answer labels.
- B2-T6: Extract labeled options such as `A.`, `B.`, `C.`, and `D.` into candidate claims.
- B2-T7: Classify non-option questions as Yes/No/Unknown, numeric, open-ended, or ambiguous.
- B2-T8: Preserve candidate label, original text, question type, and source metadata.
- B2-T9: Add tests for ambiguous option formatting and mixed question styles.
- B2-T10: Append Batch 2 execution details to `report.md`.

### Files or Modules Likely Created or Updated

- `app/cache/`
- `app/questions/`
- `tests/test_cache_keys.py`
- `tests/test_candidate_extraction.py`
- `report.md`

### Required Outputs / Artifacts

- Cache key utilities for local and API modes.
- Candidate extraction module.
- Question type classifier.
- Tests covering MCQ, Yes/No/Unknown, numeric, open-ended, and ambiguous formats.

### Acceptance Criteria

- Local and API premise cache keys are distinct and tested.
- MCQ candidates are extracted without reading answer labels.
- Numeric/open-ended classification is based on question text and candidate structure only.
- Candidate objects preserve original source text.

### Required Tests or Validations

- `python -m unittest tests/test_cache_keys.py`
- `python -m unittest tests/test_candidate_extraction.py`
- Existing Batch 1 tests.

### Explicit Non-Goals

- Do not implement LLM parse-frame extraction.
- Do not decide final answers.
- Do not route numeric questions by record ID or gold labels.

### Completion Checklist

- [x] Local/API cache key utilities exist.
- [x] Candidate extraction works for expected question types.
- [x] Tests prove no answer-label dependency.
- [x] `report.md` contains Batch 2 result.

## Mandatory Batch 3 - Parse Frame, Typed AST Schema, Compilation, Validation, and Normalization

### Goal

Define the compact parse-frame contract, typed logic AST, deterministic frame-to-AST compiler, validators, and normalizers.

### Why this batch exists

Every later reasoning layer depends on stable semantics. The LLM must produce compact frames, while deterministic code owns formal AST construction and validation.

### Inputs / Dependencies

- Batch 1 and Batch 2 outputs.
- `PLAN.md` section 5.
- `flow.md` sections on parse frames, numeric frames, frame-to-AST compilation, AST validation, and normalization.

### Exact Task List

- B3-T1: Implement parse-frame models for `rule`, `fact`, `claim`, `compound`, and `ambiguous`.
- B3-T2: Implement frame slot models for `predicate`, `numeric_condition`, `numeric_value`, `arithmetic_expression`, and `entity_relation`.
- B3-T3: Implement typed AST node models for `pred`, `not`, `and`, `or`, `implies`, `forall`, `exists`, `compare`, `arith`, and `num_ref`.
- B3-T4: Implement term models for variables, constants, and numbers.
- B3-T5: Implement frame validation for required slots, allowed enums, source metadata, numeric operators, and ambiguous frames.
- B3-T6: Implement deterministic frame-to-AST compilation for rules, facts, claims, numeric slots, and source metadata.
- B3-T7: Implement AST validation for metadata, variable binding, predicate arity, numeric operands, and malformed scopes.
- B3-T8: Implement normalization for predicate names, associative connectives, double negation, and metadata preservation.
- B3-T9: Preserve nested implications as tree structures; do not rewrite implication direction during normalization.
- B3-T10: Add tests for valid/invalid frames, compiler outputs, AST validation failures, and source metadata survival.
- B3-T11: Append Batch 3 execution details to `report.md`.

### Files or Modules Likely Created or Updated

- `app/logic/frames/`
- `app/logic/compiler/`
- `app/logic/ast/`
- `app/logic/validation/`
- `app/logic/normalization/`
- `tests/test_parse_frames.py`
- `tests/test_frame_compiler.py`
- `tests/test_logic_ast.py`
- `report.md`

### Required Outputs / Artifacts

- Parse-frame schema/models.
- Typed AST schema/models.
- Deterministic frame-to-AST compiler.
- Frame and AST validators.
- Normalization utilities.
- Tests for schema and compiler behavior.

### Acceptance Criteria

- All required parse-frame kinds validate.
- Rule/fact/claim frames compile to expected AST structures.
- Numeric frame slots compile into numeric AST nodes.
- Invalid scopes and malformed numeric expressions fail clearly.
- Source metadata survives compilation and normalization.

### Required Tests or Validations

- `python -m unittest tests/test_parse_frames.py`
- `python -m unittest tests/test_frame_compiler.py`
- `python -m unittest tests/test_logic_ast.py`
- Relevant earlier tests.

### Explicit Non-Goals

- Do not call the LLM.
- Do not implement Horn/Z3 solving.
- Do not infer answers from examples or gold annotations.

### Completion Checklist

- [ ] Parse-frame models exist.
- [ ] Typed AST models exist.
- [ ] Frame-to-AST compiler exists.
- [ ] Validation and normalization tests pass.
- [ ] `report.md` contains Batch 3 result.

## Mandatory Batch 4 - Debug Trace and Proof Trace Infrastructure

### Goal

Create structured proof trace and debug trace infrastructure before adding complex parsing and reasoning.

### Why this batch exists

The project needs root-cause visibility. Later LLM, numeric, symbolic, fallback, and API failures must be explainable by stage.

### Inputs / Dependencies

- Batches 1-3 outputs.
- `PLAN.md` section 8.
- `flow.md` section 12.

### Exact Task List

- B4-T1: Define debug trace schema with `sample_id`, `record_id`, `question_id`, stage statuses, timestamps/durations, cache metadata, warnings, and root-cause category.
- B4-T2: Define proof trace step schema with used premises, derived facts, solver route, numeric derivations, and source citations.
- B4-T3: Add root-cause categories for data validation, question parsing, LLM frame extraction, frame validation, frame compilation, AST validation, numeric failure, solver unsupported, Z3 encoding, fallback, timeout, and output formatting.
- B4-T4: Implement safe serialization and secret redaction for traces.
- B4-T5: Implement JSON/JSONL artifact writers for local debug output.
- B4-T6: Add tests that traces serialize safely and never include `.env` secrets or reference-only fields.
- B4-T7: Append Batch 4 execution details to `report.md`.

### Files or Modules Likely Created or Updated

- `app/tracing/`
- `tests/test_debug_trace.py`
- `report.md`

### Required Outputs / Artifacts

- Debug trace schema and serializer.
- Proof trace step schema.
- Root-cause category list.
- Safe JSON/JSONL artifact writing utility.

### Acceptance Criteria

- Trace serialization is deterministic and secret-safe.
- Root-cause categories are stable and test-covered.
- Trace objects can reference runtime IDs without containing gold answers or FOL.

### Required Tests or Validations

- `python -m unittest tests/test_debug_trace.py`
- Earlier tests that may interact with trace models.

### Explicit Non-Goals

- Do not implement actual LLM calls or solver routes.
- Do not generate public explanations yet.
- Do not include raw API keys or reference-only fields in fixtures.

### Completion Checklist

- [ ] Debug trace schema exists.
- [ ] Proof trace schema exists.
- [ ] Redaction tests pass.
- [ ] `report.md` contains Batch 4 result.

## Mandatory Batch 5 - LLM Parse-Frame Extractor with Mockable Runtime

### Goal

Extract compact parse frames from premises and candidates using the configured `.env` LLM client, with validation, retries, repair, and caching.

### Why this batch exists

The LLM is the semantic parser in the approved flow. This batch connects natural language to parse frames while keeping solving deterministic and testable.

### Inputs / Dependencies

- Batches 1-4 outputs.
- `.env` config with ShopAIKey/OpenAI-compatible endpoint and `SHOPAIKEY_MODEL`.
- `PLAN.md` section 6.
- `flow.md` sections 4 and 5.

### Exact Task List

- B5-T1: Define a frame extractor interface that accepts only runtime text and source metadata.
- B5-T2: Implement a mock frame extractor for deterministic tests.
- B5-T3: Implement async ShopAIKey/OpenAI-compatible HTTP client reading `SHOPAIKEY_BASE_URL`, `SHOPAIKEY_API_KEY`, and `SHOPAIKEY_MODEL` from config.
- B5-T4: Build separate prompt templates for premise frame extraction and candidate frame extraction.
- B5-T5: Enforce strict JSON parsing and parse-frame validation.
- B5-T6: Implement repair prompts that include only original runtime text and validation errors.
- B5-T7: Implement transient failure retry with exponential backoff and jitter.
- B5-T8: Cache parse frames by normalized source text, prompt version, extractor version, and model identifier.
- B5-T9: Track model identifier, prompt version, attempts, repair count, cache hit, and sanitized errors in debug traces.
- B5-T10: Add tests for valid mock frame, invalid frame repair, transient retry, cache hit, and reference-field exclusion.
- B5-T11: Add optional credential-gated live smoke validation if environment access is available; report honestly if skipped.
- B5-T12: Append Batch 5 execution details to `report.md`.

### Files or Modules Likely Created or Updated

- `app/llm/`
- prompt templates under `app/llm/` or equivalent
- `tests/test_llm_frame_extraction.py`
- `report.md`

### Required Outputs / Artifacts

- Mockable LLM frame extractor.
- Configured async HTTP client.
- Prompt templates for premise and candidate parsing.
- Repair and retry behavior.
- Parse-frame cache.
- Tests for extraction behavior.

### Acceptance Criteria

- Mocked valid frame succeeds.
- Invalid first-pass frame triggers repair.
- Transient failures retry with backoff.
- Runtime frame extractor input excludes `premises-FOL`, `answer`, `explanation`, and `idx`.
- Production path uses configured `.env` model and does not silently switch provider.

### Required Tests or Validations

- `python -m unittest tests/test_llm_frame_extraction.py`
- Relevant previous tests.
- Optional live smoke command only if safe credentials/service are available.

### Explicit Non-Goals

- Do not let the LLM answer questions.
- Do not ask the LLM for full ASTs in the main path.
- Do not include gold FOL or gold answers in prompts.

### Completion Checklist

- [ ] Frame extractor interface exists.
- [ ] Mock extractor exists.
- [ ] Configured async client exists.
- [ ] Repair/retry/cache behavior is tested.
- [ ] `report.md` contains Batch 5 result.

## Mandatory Batch 6 - Async Pipeline, Premise Cache, and Single-Flight Locks

### Goal

Implement runtime orchestration for local and API-style samples with bounded concurrency, premise caching, and single-flight locks.

### Why this batch exists

The project will call an LLM through an API key. Without async execution and shared premise conversion, local evaluation will be too slow and redundant.

### Inputs / Dependencies

- Batches 1-5 outputs.
- `PLAN.md` section 9.
- `flow.md` section 3.

### Exact Task List

- B6-T1: Implement bounded async scheduler for local flattened samples.
- B6-T2: Implement local premise cache keyed by `record:<record_id>`.
- B6-T3: Implement API premise cache keyed by `premises_hash:<hash>`.
- B6-T4: Implement single-flight locks so concurrent requests for the same premise set trigger one conversion.
- B6-T5: Implement per-request and per-sample timeout handling.
- B6-T6: Ensure one failed sample does not stop the batch.
- B6-T7: Preserve output ordering by `record_id`, then `question_id`.
- B6-T8: Orchestrate premise frame extraction, premise compilation, candidate extraction, candidate frame extraction, candidate compilation, and trace creation up to solver handoff.
- B6-T9: Write preliminary prediction/debug artifacts even for failed or unsupported samples.
- B6-T10: Add tests for concurrency, cache sharing, single-flight behavior, timeout, failure isolation, and output ordering.
- B6-T11: Append Batch 6 execution details to `report.md`.

### Files or Modules Likely Created or Updated

- `app/pipeline/`
- `scripts/evaluate_local.py`
- `tests/test_async_pipeline.py`
- `report.md`

### Required Outputs / Artifacts

- Async local evaluation scheduler.
- API-style single-query pipeline entrypoint.
- Premise cache abstraction supporting both key modes.
- Single-flight lock registry.
- Debug artifact writing path.

### Acceptance Criteria

- Concurrent local samples sharing a record trigger one premise conversion.
- Repeated API-style requests with same premise text trigger one premise conversion.
- Failed samples produce traceable artifacts and do not stop the batch.
- Output order is deterministic.

### Required Tests or Validations

- `python -m unittest tests/test_async_pipeline.py`
- Earlier tests.

### Explicit Non-Goals

- Do not implement numeric solver or symbolic solver logic beyond stubs required for handoff.
- Do not implement final API endpoint yet.
- Do not score against gold answers in runtime.

### Completion Checklist

- [ ] Async scheduler exists.
- [ ] Local/API cache modes exist.
- [ ] Single-flight locks are tested.
- [ ] Failure isolation works.
- [ ] `report.md` contains Batch 6 result.

## Mandatory Batch 7 - Numeric Layer with Source Provenance

### Goal

Extract, evaluate, and trace numeric facts and constraints before symbolic solving.

### Why this batch exists

Some records require numerical reasoning. The system must detect numeric reasoning from parse frames/AST nodes, not keywords, record IDs, or hardcoded examples.

### Inputs / Dependencies

- Batches 1-6 outputs.
- `flow.md` section 5.
- `PLAN.md` numeric requirements in sections 6 and 12 Batch 7.

### Exact Task List

- B7-T1: Extract numeric facts from validated parse-frame numeric slots.
- B7-T2: Extract numeric facts from compiled AST numeric nodes.
- B7-T3: Add source-text supplemental extraction only when validated frames/ASTs lack enough detail.
- B7-T4: Preserve provenance for every quantity: source ID, source text, premise ID or candidate label, and character/span metadata when available.
- B7-T5: Evaluate deterministic arithmetic such as percentages, averages, thresholds, weighted scores, fees, and date/time offsets.
- B7-T6: Insert derived numeric facts into solver context and proof trace.
- B7-T7: Detect conflicts between AST-derived and source-text-derived numeric facts; prefer validated AST and trace the conflict.
- B7-T8: Route harder numeric constraints to Z3-compatible forms.
- B7-T9: Add tests for percentages, GPA, scores, averages, thresholds, durations, and comparison phrases.
- B7-T10: Add tests proving numeric routing is based on numeric frame/AST features, not record IDs.
- B7-T11: Append Batch 7 execution details to `report.md`.

### Files or Modules Likely Created or Updated

- `app/numeric/`
- `tests/test_numeric_layer.py`
- `report.md`

### Required Outputs / Artifacts

- Numeric extractor.
- Deterministic numeric evaluator.
- Numeric provenance model.
- Numeric proof-trace integration.
- Tests for numeric scenarios.

### Acceptance Criteria

- Numeric derived facts cite their source premises/candidates.
- Percentages, averages, thresholds, and time comparisons are covered.
- Numeric parse failures produce traceable warnings.
- No numeric route depends on sample ID, record ID, question ID, or gold answer.

### Required Tests or Validations

- `python -m unittest tests/test_numeric_layer.py`
- Relevant earlier tests.

### Explicit Non-Goals

- Do not implement full Z3 adapter logic beyond producing compatible constraints for later routing.
- Do not hardcode values from `record_0034_question_0000` or any other dataset record.
- Do not use gold explanations to infer formulas.

### Completion Checklist

- [ ] Numeric extraction exists.
- [ ] Deterministic arithmetic works for required cases.
- [ ] Provenance is preserved.
- [ ] Anti-hardcode numeric tests pass.
- [ ] `report.md` contains Batch 7 result.

## Mandatory Batch 8 - Horn Prover, Contraposition, Quantifier Instantiation, and Entailment Decision

### Goal

Implement core symbolic reasoning and answer decision for MCQ and Yes/No/Unknown cases.

### Why this batch exists

The system needs deterministic proof-backed reasoning before extended Z3/fallback behavior. This is the main scoring path for many logic questions.

### Inputs / Dependencies

- Batches 1-7 outputs.
- `PLAN.md` symbolic verification section.
- `flow.md` sections 9 and 10.

### Exact Task List

- B8-T1: Extract ground facts and Horn-compatible rules from validated ASTs.
- B8-T2: Implement forward chaining for Horn rules.
- B8-T3: Implement claim and negated-claim entailment checks.
- B8-T4: Implement safe contraposition only for explicit literal-to-literal implication cases described in the plan.
- B8-T5: Reject unsafe contraposition cases clearly with `solver_capability_gap`.
- B8-T6: Implement schema-level universal matching for generic universal premise/candidate formulas.
- B8-T7: Instantiate universal rules over discovered constants only.
- B8-T8: Support bounded existential candidate satisfaction where grounded evidence exists.
- B8-T9: Implement Yes/No/Unknown answer decision.
- B8-T10: Implement local MCQ answer selection with `Unknown` allowed when no unique option is provable.
- B8-T11: Add proof trace steps for every derived fact and answer decision.
- B8-T12: Add tests for Horn rules, safe/unsafe contraposition, quantifiers, candidate entailment, and answer decision.
- B8-T13: Append Batch 8 execution details to `report.md`.

### Files or Modules Likely Created or Updated

- `app/solver/horn/`
- `app/solver/contraposition/`
- `app/solver/quantifiers/`
- `app/output/decision/`
- `tests/test_horn_solver.py`
- `tests/test_contraposition.py`
- `tests/test_quantifiers.py`
- `tests/test_answer_decision.py`
- `report.md`

### Required Outputs / Artifacts

- Horn prover.
- Safe contraposition module.
- Bounded quantifier utilities.
- Entailment result model.
- Answer decision module.
- Proof trace integration.

### Acceptance Criteria

- Supported Horn cases are proven deterministically.
- Safe contraposition cases pass and unsafe cases are rejected.
- Supported quantifier cases instantiate over discovered constants only.
- Unknown is returned when neither claim nor negation is entailed.
- MCQ local behavior can return `Unknown` when no unique option is proved.

### Required Tests or Validations

- `python -m unittest tests/test_horn_solver.py`
- `python -m unittest tests/test_contraposition.py`
- `python -m unittest tests/test_quantifiers.py`
- `python -m unittest tests/test_answer_decision.py`
- Relevant earlier tests.

### Explicit Non-Goals

- Do not encode non-Horn fragments in Z3 yet.
- Do not implement semantic fallback.
- Do not force MCQ choices for official submission yet.

### Completion Checklist

- [ ] Horn prover exists.
- [ ] Safe contraposition is tested.
- [ ] Quantifier behavior is bounded and tested.
- [ ] Answer decision works.
- [ ] `report.md` contains Batch 8 result.

## Mandatory Batch 9 - Z3 Adapter, Nested Implication Routing, and Semantic Fallback

### Goal

Extend solver coverage to supported numeric/non-Horn fragments and add a confidence-capped fallback when symbolic routes cannot answer.

### Why this batch exists

Some dataset questions include arithmetic, grounded Boolean constraints, or nested implication patterns that exceed Horn reasoning. Unsupported cases must be traceable rather than silently guessed.

### Inputs / Dependencies

- Batches 1-8 outputs.
- `PLAN.md` Z3 and semantic fallback sections.
- `flow.md` symbolic verification section.

### Exact Task List

- B9-T1: Implement solver feature detection and route selection.
- B9-T2: Route Horn-compatible cases to the Horn prover.
- B9-T3: Encode grounded numeric and Boolean constraints into Z3-compatible forms.
- B9-T4: Encode nested implications only when fully grounded into finite Boolean formulas.
- B9-T5: Mark unsupported nested/meta-logic cases as `solver_capability_gap`.
- B9-T6: Implement semantic fallback verifier for cases where symbolic routes cannot produce a strong result.
- B9-T7: Cap fallback confidence below successful symbolic proof confidence.
- B9-T8: Prevent fallback from overriding a symbolic proof.
- B9-T9: Record solver route, unsupported features, Z3 status, fallback use, and confidence penalties in traces.
- B9-T10: Add tests for route selection, supported Z3 cases, unsupported nested implication, fallback confidence cap, and fallback override prevention.
- B9-T11: Append Batch 9 execution details to `report.md`.

### Files or Modules Likely Created or Updated

- `app/solver/router/`
- `app/solver/z3_adapter/`
- `app/solver/semantic_fallback/`
- `tests/test_solver_routing.py`
- `tests/test_z3_adapter.py`
- `tests/test_semantic_fallback.py`
- `report.md`

### Required Outputs / Artifacts

- Solver router.
- Z3 adapter for grounded supported fragments.
- Semantic fallback verifier.
- Confidence and trace integration.

### Acceptance Criteria

- Z3 handles supported numeric and grounded nested implication cases.
- Unsupported nested implication returns `solver_capability_gap`.
- Fallback cannot override symbolic proof.
- Fallback confidence is capped and trace-visible.

### Required Tests or Validations

- `python -m unittest tests/test_solver_routing.py`
- `python -m unittest tests/test_z3_adapter.py`
- `python -m unittest tests/test_semantic_fallback.py`
- Relevant earlier tests.

### Explicit Non-Goals

- Do not implement unrestricted natural deduction or meta-logic.
- Do not let fallback guess from gold labels.
- Do not overfit Z3 encodings to individual dataset records.

### Completion Checklist

- [ ] Solver router exists.
- [ ] Z3 adapter handles supported fragments.
- [ ] Unsupported fragments are explicit.
- [ ] Semantic fallback is confidence-capped.
- [ ] `report.md` contains Batch 9 result.

## Mandatory Batch 10 - Explanation Generation, Open-Ended Output, and MCQ Submission Adapter

### Goal

Produce public-facing answers and explanations from proof traces, including configurable MCQ submission behavior and best-effort open-ended handling.

### Why this batch exists

The competition requires `answer` and `explanation`. These outputs must be grounded in proof traces, not free-form LLM reasoning.

### Inputs / Dependencies

- Batches 1-9 outputs.
- `PLAN.md` output and MCQ policy sections.
- `flow.md` sections 10 and 11.

### Exact Task List

- B10-T1: Implement explanation rendering from proof trace steps.
- B10-T2: Cite premise numbers, computed values, contraposition route, Z3 route, or fallback route when used.
- B10-T3: Implement public response formatting with required `answer` and `explanation`.
- B10-T4: Include optional `fol`, `cot`, `premises`, and `confidence` fields only when safe and grounded.
- B10-T5: Implement best-effort open-ended short answers using only entailed proof-trace facts.
- B10-T6: Return `Unknown` with low confidence when no grounded open-ended answer exists.
- B10-T7: Implement local MCQ policy allowing `Unknown`.
- B10-T8: Implement official MCQ submission adapter with configurable forced-choice behavior if evaluator requires `A/B/C/D`.
- B10-T9: Ensure forced-choice traces include internal answer, selected fallback option, candidate scores, threshold, confidence penalty, and reason.
- B10-T10: Add tests for proof-trace explanation, open-ended grounding, local MCQ policy, and submission adapter behavior.
- B10-T11: Append Batch 10 execution details to `report.md`.

### Files or Modules Likely Created or Updated

- `app/output/explanation/`
- `app/output/format/`
- `app/output/mcq_submission_adapter/`
- `tests/test_explanation_output.py`
- `tests/test_open_ended_output.py`
- `tests/test_mcq_submission_adapter.py`
- `report.md`

### Required Outputs / Artifacts

- Explanation renderer.
- Public response formatter.
- Open-ended output handler.
- MCQ submission adapter.
- Tests for public output behavior.

### Acceptance Criteria

- Explanations reference only proof trace facts.
- Open-ended answers do not invent unsupported content.
- MCQ local and official submission behavior are tested separately.
- Optional evidence fields do not leak secrets or reference-only data.

### Required Tests or Validations

- `python -m unittest tests/test_explanation_output.py`
- `python -m unittest tests/test_open_ended_output.py`
- `python -m unittest tests/test_mcq_submission_adapter.py`
- Relevant earlier tests.

### Explicit Non-Goals

- Do not change core solver decisions to make explanations prettier.
- Do not use an LLM to invent explanations outside proof trace.
- Do not assume the official MCQ evaluator accepts `Unknown`.

### Completion Checklist

- [ ] Explanation renderer exists.
- [ ] Public response formatter exists.
- [ ] Open-ended behavior is proof-grounded.
- [ ] MCQ adapter is configurable and tested.
- [ ] `report.md` contains Batch 10 result.

## Mandatory Batch 11 - API Endpoint

### Goal

Expose a competition-compatible prediction API that accepts only `premises-NL` and `question`.

### Why this batch exists

The final system must be callable by an evaluator. The API must use API premise-hash caching, not local `record_id`.

### Inputs / Dependencies

- Batches 1-10 outputs.
- `PLAN.md` API submission section.
- `flow.md` runtime input/API shape section.

### Exact Task List

- B11-T1: Implement proposed `POST /predict` endpoint unless the official spec provides a different path before execution.
- B11-T2: Validate request body shape: `premises-NL: list[str]`, `question: str`.
- B11-T3: Reject malformed requests with safe validation errors.
- B11-T4: Use API premise-hash cache, not `record_id`.
- B11-T5: Call the runtime pipeline for one query.
- B11-T6: Return schema-compliant public response with `answer` and `explanation`, plus safe optional evidence.
- B11-T7: Redact internal errors and secrets from API responses.
- B11-T8: Add API tests for valid request, malformed request, cache mode, reference-field rejection, and safe errors.
- B11-T9: Append Batch 11 execution details to `report.md`.

### Files or Modules Likely Created or Updated

- `app/api/`
- `tests/test_api.py`
- API server entrypoint if needed
- `report.md`

### Required Outputs / Artifacts

- Prediction endpoint.
- Request/response validation.
- API runtime cache mode.
- API tests.

### Acceptance Criteria

- Valid requests return required fields.
- API does not require or accept local evaluation IDs.
- API runtime cannot access reference-only fields.
- Errors are safe and do not leak secrets.

### Required Tests or Validations

- `python -m unittest tests/test_api.py`
- Relevant earlier tests.
- API smoke test with mocked or configured model endpoint when feasible.

### Explicit Non-Goals

- Do not implement final deployment infrastructure unless required by current repo conventions.
- Do not expose debug traces publicly by default.
- Do not change official response shape without source support.

### Completion Checklist

- [ ] API endpoint exists.
- [ ] Request validation works.
- [ ] API cache mode uses premise hash.
- [ ] API tests pass.
- [ ] `report.md` contains Batch 11 result.

## Mandatory Batch 12 - Evaluation, Scoring, and Error Analysis

### Goal

Implement local evaluation, scoring, and error analysis while keeping scoring references outside runtime.

### Why this batch exists

Performance must be measurable, but labels and reference annotations must not influence runtime predictions.

### Inputs / Dependencies

- Batches 1-11 outputs.
- Flattened dataset.
- `PLAN.md` evaluation and scoring sections.

### Exact Task List

- B12-T1: Implement local evaluation script over `data/processed/Logic_Based_Educational_Queries.flattened.json`.
- B12-T2: Ensure evaluation script sanitizes each sample before inference.
- B12-T3: Write ordered `predictions.json` public-like artifact.
- B12-T4: Write sanitized `debug_traces.jsonl`.
- B12-T5: Implement scoring against `answer` only after prediction is complete.
- B12-T6: Implement error aggregation by question type, solver route, fallback use, cache mode, and root-cause category.
- B12-T7: Write `error_summary.json`.
- B12-T8: Add tests proving scorer/analyzer may read references but runtime cannot.
- B12-T9: Add small fixture smoke run for local evaluation.
- B12-T10: Append Batch 12 execution details to `report.md`.

### Files or Modules Likely Created or Updated

- `scripts/evaluate_local.py`
- `scripts/score_predictions.py`
- `scripts/analyze_errors.py`
- `tests/test_evaluation_scripts.py`
- local artifact output directory if needed
- `report.md`

### Required Outputs / Artifacts

- Local evaluation script.
- Scoring script.
- Error analysis script.
- Prediction/debug/error artifacts.
- Tests for evaluation boundaries.

### Acceptance Criteria

- Evaluation reads references only in scorer/analyzer.
- Runtime pipeline receives sanitized inputs only.
- Error summary is grouped and actionable.
- Failed samples produce traceable outputs instead of stopping the run.

### Required Tests or Validations

- `python -m unittest tests/test_evaluation_scripts.py`
- Local smoke run on a small fixture dataset.
- Relevant earlier tests.

### Explicit Non-Goals

- Do not tune runtime behavior from gold answers inside the evaluation loop.
- Do not use `premises-FOL` as runtime input.
- Do not claim full benchmark performance from a tiny smoke fixture.

### Completion Checklist

- [ ] Evaluation script exists.
- [ ] Scoring script exists.
- [ ] Error analyzer exists.
- [ ] Reference/runtime boundary tests pass.
- [ ] `report.md` contains Batch 12 result.

## Mandatory Batch 13 - Regression Suite and Final Hardening

### Goal

Stabilize the system for submission with regression tests, documentation, smoke validation, and final constraint checks.

### Why this batch exists

After all components exist, the project needs end-to-end confidence that the implementation follows competition constraints and the approved architecture.

### Inputs / Dependencies

- Batches 1-12 outputs.
- `PLAN.md` final acceptance criteria.
- `flow.md` full runtime flow.
- `docs/competition.md`.

### Exact Task List

- B13-T1: Add golden fixtures for MCQ, Yes, No, Unknown, numeric, contraposition, nested implication, quantifier, fallback, and open-ended cases.
- B13-T2: Add timeout and rate-limit regression tests.
- B13-T3: Add local/API cache hit-count regression tests.
- B13-T4: Add final leakage tests for prompts, frame extractor inputs, compiler inputs, solver inputs, explanations, debug traces, API responses, and predictions.
- B13-T5: Document configured model choice from `.env`, currently `SHOPAIKEY_MODEL=qwen2.5-7b-instruct`, without exposing secrets.
- B13-T6: Document any external data/model usage for the one-page solution description.
- B13-T7: Run the full unit test suite.
- B13-T8: Run local evaluation smoke test.
- B13-T9: Run API smoke test with mocked or configured model endpoint.
- B13-T10: Review all touched files over 200 lines and document line counts/rationale in `report.md`.
- B13-T11: Update final progress tracker and append Batch 13 execution details to `report.md`.

### Files or Modules Likely Created or Updated

- expanded tests and fixtures
- solution description draft or docs file
- final config/docs
- `report.md`

### Required Outputs / Artifacts

- Regression test fixtures.
- Final validation results.
- Model/config documentation.
- Solution description notes.
- Final `report.md` entry.

### Acceptance Criteria

- Full relevant test suite passes or any blocker is reported precisely.
- Submission response shape is valid.
- Runtime still accepts only `premises-NL` and `question`.
- Competition constraints are documented.
- No overfit/hardcode/label-leak shortcut is present.

### Required Tests or Validations

- Full unit test suite.
- Local evaluation smoke run.
- API smoke test with mocked or configured model endpoint.
- Manual review of final acceptance criteria in `PLAN.md`.

### Explicit Non-Goals

- Do not add new architecture beyond the approved flow.
- Do not optimize for specific dataset records.
- Do not hide failing validations.

### Completion Checklist

- [ ] Regression fixtures exist.
- [ ] Full tests or documented blockers exist.
- [ ] Smoke validations are run or honestly blocked.
- [ ] Final model/config docs exist.
- [ ] `report.md` contains Batch 13 result.

## Optional Future Track - Broader Dataset Type Adapters

### Possible Scope

`docs/competition.md` says the official test set will be unified across dataset types, while this repository currently contains the Type 1 logic-based dataset. If additional Type 2 specifications or files are released, add a separate adapter or pipeline extension.

### Hard Limits

- This track is outside the mandatory Batch 1-13 chain.
- Do not weaken Type 1 runtime boundaries.
- Do not merge new dataset assumptions into the core solver without source evidence.

### Possible Artifacts

- New dataset loader adapter.
- New candidate extraction extension.
- Separate evaluation metrics for the new dataset type.

## Dependency Chain Between Batches

- Batch 1 -> Batch 2: safe data/config boundary before question/candidate work.
- Batch 2 -> Batch 3: candidate/cache contracts before parse-frame and AST contracts.
- Batch 3 -> Batch 4: stable schemas before trace schemas cite them.
- Batch 4 -> Batch 5: traces before LLM failures and repairs.
- Batch 5 -> Batch 6: parse-frame extractor before async orchestration.
- Batch 6 -> Batch 7: pipeline before numeric layer integration.
- Batch 7 -> Batch 8: numeric facts before core symbolic answer decision.
- Batch 8 -> Batch 9: core symbolic solver before Z3/fallback extensions.
- Batch 9 -> Batch 10: solver results before public explanations and adapters.
- Batch 10 -> Batch 11: output formatter before API endpoint.
- Batch 11 -> Batch 12: API/runtime path before local evaluation and scoring.
- Batch 12 -> Batch 13: evaluation loop before final hardening.
- Optional future dataset adapters are outside the mandatory chain.

## Global Verification Checklist

- [ ] Runtime API accepts only `premises-NL` and `question`.
- [ ] Runtime code cannot access `premises-FOL`, `answer`, `explanation`, or `idx`.
- [ ] Local evaluation caches premise ASTs by `record_id`.
- [ ] API runtime caches premise ASTs by normalized/hash of `premises-NL`.
- [ ] Both cache modes use single-flight locks.
- [ ] Async evaluation supports bounded concurrency, retries, backoff, timeout handling, failed-sample continuation, and deterministic output ordering.
- [ ] Parse-frame schema and AST schema support required logical/numeric constructs, metadata, variables/constants, deterministic compilation, and strict validation.
- [ ] Numeric layer tracks source provenance and inserts derived facts into proof trace.
- [ ] Horn prover supports tested safe contraposition.
- [ ] Quantifier handling supports schema-level universal matching, bounded instantiation, and unsupported-case reporting.
- [ ] Nested implications are routed to grounded Z3 encoding or explicit `solver_capability_gap`.
- [ ] Semantic fallback exists, is confidence-capped, and does not override symbolic proofs.
- [ ] MCQ local `Unknown` and official submission adapter behavior are tested separately.
- [ ] Best-effort open-ended answers are proof-grounded or return `Unknown`.
- [ ] Explanations are generated from proof traces only.
- [ ] Debug traces identify root causes without leaking secrets.
- [ ] Model configuration uses `.env` as source of truth and documents `SHOPAIKEY_MODEL` without exposing the API key.
- [ ] Evaluation scripts score predictions only outside runtime.
- [ ] NO DATA OVERFITTING: no record-specific tuning, answer leakage, gold-FOL leakage, or dataset-row shortcuts.
- [ ] NO HARDCODING: no hardcoded answers, entity lists, predicate maps, numeric thresholds, or record-specific rule branches.
- [ ] Every touched file over 200 lines is reported in `report.md` with line count and rationale.
- [ ] `report.md` has a detailed entry for every completed batch.

## Progress Tracker

### Batches

- [x] Batch 1 - Foundation, Config, and Runtime-Safe Data Layer
- [x] Batch 2 - Cache Keys, Candidate Extraction, and Question Typing
- [ ] Batch 3 - Parse Frame, Typed AST Schema, Compilation, Validation, and Normalization
- [ ] Batch 4 - Debug Trace and Proof Trace Infrastructure
- [ ] Batch 5 - LLM Parse-Frame Extractor with Mockable Runtime
- [ ] Batch 6 - Async Pipeline, Premise Cache, and Single-Flight Locks
- [ ] Batch 7 - Numeric Layer with Source Provenance
- [ ] Batch 8 - Horn Prover, Contraposition, Quantifier Instantiation, and Entailment Decision
- [ ] Batch 9 - Z3 Adapter, Nested Implication Routing, and Semantic Fallback
- [ ] Batch 10 - Explanation Generation, Open-Ended Output, and MCQ Submission Adapter
- [ ] Batch 11 - API Endpoint
- [ ] Batch 12 - Evaluation, Scoring, and Error Analysis
- [ ] Batch 13 - Regression Suite and Final Hardening

### Milestones

- [x] M1 - Runtime-Safe Foundation
- [x] M2 - Query Contract
- [ ] M3 - Logic Representation Contract
- [ ] M4 - Observability Foundation
- [ ] M5 - LLM Semantic Parser
- [ ] M6 - Async Runtime Skeleton
- [ ] M7 - Numeric Reasoning Layer
- [ ] M8 - Core Symbolic Reasoning
- [ ] M9 - Extended Verification
- [ ] M10 - Public Output Layer
- [ ] M11 - Submission API
- [ ] M12 - Evaluation Loop
- [ ] M13 - Final Hardening

### Task IDs

- [x] B1-T1
- [x] B1-T2
- [x] B1-T3
- [x] B1-T4
- [x] B1-T5
- [x] B1-T6
- [x] B1-T7
- [x] B1-T8
- [x] B1-T9
- [x] B2-T1
- [x] B2-T2
- [x] B2-T3
- [x] B2-T4
- [x] B2-T5
- [x] B2-T6
- [x] B2-T7
- [x] B2-T8
- [x] B2-T9
- [x] B2-T10
- [ ] B3-T1
- [ ] B3-T2
- [ ] B3-T3
- [ ] B3-T4
- [ ] B3-T5
- [ ] B3-T6
- [ ] B3-T7
- [ ] B3-T8
- [ ] B3-T9
- [ ] B3-T10
- [ ] B3-T11
- [ ] B4-T1
- [ ] B4-T2
- [ ] B4-T3
- [ ] B4-T4
- [ ] B4-T5
- [ ] B4-T6
- [ ] B4-T7
- [ ] B5-T1
- [ ] B5-T2
- [ ] B5-T3
- [ ] B5-T4
- [ ] B5-T5
- [ ] B5-T6
- [ ] B5-T7
- [ ] B5-T8
- [ ] B5-T9
- [ ] B5-T10
- [ ] B5-T11
- [ ] B5-T12
- [ ] B6-T1
- [ ] B6-T2
- [ ] B6-T3
- [ ] B6-T4
- [ ] B6-T5
- [ ] B6-T6
- [ ] B6-T7
- [ ] B6-T8
- [ ] B6-T9
- [ ] B6-T10
- [ ] B6-T11
- [ ] B7-T1
- [ ] B7-T2
- [ ] B7-T3
- [ ] B7-T4
- [ ] B7-T5
- [ ] B7-T6
- [ ] B7-T7
- [ ] B7-T8
- [ ] B7-T9
- [ ] B7-T10
- [ ] B7-T11
- [ ] B8-T1
- [ ] B8-T2
- [ ] B8-T3
- [ ] B8-T4
- [ ] B8-T5
- [ ] B8-T6
- [ ] B8-T7
- [ ] B8-T8
- [ ] B8-T9
- [ ] B8-T10
- [ ] B8-T11
- [ ] B8-T12
- [ ] B8-T13
- [ ] B9-T1
- [ ] B9-T2
- [ ] B9-T3
- [ ] B9-T4
- [ ] B9-T5
- [ ] B9-T6
- [ ] B9-T7
- [ ] B9-T8
- [ ] B9-T9
- [ ] B9-T10
- [ ] B9-T11
- [ ] B10-T1
- [ ] B10-T2
- [ ] B10-T3
- [ ] B10-T4
- [ ] B10-T5
- [ ] B10-T6
- [ ] B10-T7
- [ ] B10-T8
- [ ] B10-T9
- [ ] B10-T10
- [ ] B10-T11
- [ ] B11-T1
- [ ] B11-T2
- [ ] B11-T3
- [ ] B11-T4
- [ ] B11-T5
- [ ] B11-T6
- [ ] B11-T7
- [ ] B11-T8
- [ ] B11-T9
- [ ] B12-T1
- [ ] B12-T2
- [ ] B12-T3
- [ ] B12-T4
- [ ] B12-T5
- [ ] B12-T6
- [ ] B12-T7
- [ ] B12-T8
- [ ] B12-T9
- [ ] B12-T10
- [ ] B13-T1
- [ ] B13-T2
- [ ] B13-T3
- [ ] B13-T4
- [ ] B13-T5
- [ ] B13-T6
- [ ] B13-T7
- [ ] B13-T8
- [ ] B13-T9
- [ ] B13-T10
- [ ] B13-T11

## Completion Reporting Rules for Future AI Execution Agents

Future execution agents must report batch progress in a structured way and must not claim completion until acceptance criteria and required validations are satisfied.

Every completed batch must append a detailed section to the shared `report.md`. Because many batches use the same report file, append new sections instead of replacing prior batch reports.

### Required `report.md` Section Template

```markdown
## Batch X Execution Result - YYYY-MM-DD

### Completed Tasks
List the task IDs that are done.

### Files Created or Modified
List exact files touched in the batch.

### Files Over 200 Lines
List every touched file over 200 lines with line count and rationale. If none, write `None`.

### Tests or Validations Run
List commands run and relevant outcomes.

### Acceptance Criteria Check
State which criteria were met and which remain open.

### Artifacts Produced
List logs, summaries, outputs, predictions, debug traces, or generated files.

### Checklist Update
State which batch, milestone, and task IDs should be checked off in `task.md`.

### Key Implementation Decisions
Document important design or boundary decisions.

### Risks or Open Issues
Call out anything that still needs attention.

### Minor Issues Fixed During Execution
List small corrections made while working.

### Workflow Integrity Check
Confirm:
- Runtime did not use reference-only fields.
- No overfit or hardcode shortcut was introduced.
- `.env` secrets were not logged or written.
- Architecture still follows `flow.md` and `PLAN.md`.
- Required validations were run or blockers were reported honestly.

### Notes for Next Batch
State exact handoff conditions for the next batch.
```

### Final Response Rule for Execution Agents

At the end of a batch, the execution agent's final user-facing response should summarize:

- batch completed or blocked;
- main files touched;
- validations run;
- location of the appended `report.md` section;
- any unresolved risks.

Do not claim a batch is complete if required tests were not run and no honest blocker is documented.
