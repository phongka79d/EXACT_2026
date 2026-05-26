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
- Starting with the next unfinished batch after this rule is added, run an early credential-gated LLM connectivity smoke check before adding more downstream logic if no successful live LLM smoke has already been recorded in `report.md`.
- The early LLM smoke check must use `.env` values for `SHOPAIKEY_BASE_URL`, `SHOPAIKEY_API_KEY`, and `SHOPAIKEY_MODEL`, send only a tiny runtime-safe prompt, validate basic response shape, and redact all secrets.
- When the LLM parse-frame extractor is implemented, run a second live smoke check that requests strict compact parse-frame JSON and validates the returned frame shape.

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
- M8.5 - Numeric Layer Maintainability
  - Batch 8.5 complete. The Batch 7 numeric layer is split into focused modules without changing runtime behavior.
- M8.6 - LLM Parser Prompt Hardening
  - Batch 8.6 complete. Premise and candidate parse-frame prompts are stronger, schema-grounded, and tested with live/runtime-safe parser smoke.
- M9 - Extended Verification
  - Batch 9 complete. Z3 routing and confidence-capped fallback cover supported harder fragments.
- M9.5 - Solver Citation Enrichment
  - Batch 9.5 complete. Solver proof steps preserve source text and citation metadata needed by public explanations.
- M9.6 - Proof Trace Explanation Readiness
  - Batch 9.6 complete. Proof traces are explanation-ready before public output formatting and adapters.
- M9.7 - Parser/AST Canonicalization Hardening
  - Batch 9.7 not yet complete. Bundle-local parser/AST canonicalization has been hardened, but live provider-stable smoke acceptance is still pending.
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
8. Batch 8 -> Batch 8.5
9. Batch 8.5 -> Batch 8.6
10. Batch 8.6 -> Batch 9
11. Batch 9 -> Batch 9.5
12. Batch 9.5 -> Batch 9.6
13. Batch 9.6 -> Batch 9.7
14. Batch 9.7 -> Batch 10
15. Batch 10 -> Batch 11
16. Batch 11 -> Batch 12
17. Batch 12 -> Batch 13

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
- Do not call the live LLM API for parse-frame extraction or answering in Batch 1; later batches may run credential-gated smoke checks as required by the global live LLM validation rule.
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

- [x] Parse-frame models exist.
- [x] Typed AST models exist.
- [x] Frame-to-AST compiler exists.
- [x] Validation and normalization tests pass.
- [x] `report.md` contains Batch 3 result.

## Mandatory Batch 4 - Debug Trace and Proof Trace Infrastructure

### Goal

Create structured proof trace and debug trace infrastructure before adding complex parsing and reasoning, and validate live LLM connectivity early enough to catch provider/config issues before Batch 5.

### Why this batch exists

The project needs root-cause visibility. Later LLM, numeric, symbolic, fallback, and API failures must be explainable by stage.

### Inputs / Dependencies

- Batches 1-3 outputs.
- `PLAN.md` section 8.
- `flow.md` section 12.

### Exact Task List

- B4-T1: Add or run an early credential-gated LLM connectivity smoke check using `.env` if no successful live LLM smoke has already been recorded in `report.md`.
- B4-T2: Ensure the smoke check validates authentication/model availability/basic response shape with a tiny runtime-safe prompt and never prints raw `.env` secrets.
- B4-T3: Define debug trace schema with `sample_id`, `record_id`, `question_id`, stage statuses, timestamps/durations, cache metadata, warnings, and root-cause category.
- B4-T4: Define proof trace step schema with used premises, derived facts, solver route, numeric derivations, and source citations.
- B4-T5: Add root-cause categories for data validation, question parsing, LLM frame extraction, frame validation, frame compilation, AST validation, numeric failure, solver unsupported, Z3 encoding, fallback, timeout, and output formatting.
- B4-T6: Implement safe serialization and secret redaction for traces.
- B4-T7: Implement JSON/JSONL artifact writers for local debug output.
- B4-T8: Add tests that traces serialize safely and never include `.env` secrets or reference-only fields.
- B4-T9: Append Batch 4 execution details to `report.md`.

### Files or Modules Likely Created or Updated

- `app/tracing/`
- `tests/test_debug_trace.py`
- `report.md`

### Required Outputs / Artifacts

- Debug trace schema and serializer.
- Proof trace step schema.
- Root-cause category list.
- Safe JSON/JSONL artifact writing utility.
- Early LLM connectivity smoke result recorded in `report.md` as passed, failed, or blocked with sanitized details.

### Acceptance Criteria

- Trace serialization is deterministic and secret-safe.
- Root-cause categories are stable and test-covered.
- Trace objects can reference runtime IDs without containing gold answers or FOL.
- Live LLM connectivity has been tested from `.env` when credentials/service are available, or the exact sanitized blocker is documented.

### Required Tests or Validations

- `python -m unittest tests/test_debug_trace.py`
- Earlier tests that may interact with trace models.
- Early LLM connectivity smoke command using configured `.env`, or a documented blocked live validation with sanitized details.

### Explicit Non-Goals

- Do not implement LLM parse-frame extraction or solver routes.
- Do not generate public explanations yet.
- Do not include raw API keys or reference-only fields in fixtures.

### Completion Checklist

- [x] Debug trace schema exists.
- [x] Proof trace schema exists.
- [x] Redaction tests pass.
- [x] Early LLM connectivity smoke is passed or honestly reported as blocked.
- [x] `report.md` contains Batch 4 result.

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
- B5-T11: Add required credential-gated live parse-frame smoke validation when `.env` contains `SHOPAIKEY_BASE_URL`, `SHOPAIKEY_API_KEY`, and `SHOPAIKEY_MODEL`; report sanitized blockers honestly if provider access fails.
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
- Live parse-frame smoke succeeds when provider access is available, or the blocker is documented with sanitized details.

### Required Tests or Validations

- `python -m unittest tests/test_llm_frame_extraction.py`
- Relevant previous tests.
- Live parse-frame smoke command using configured `.env` model when required settings are present, or a documented blocked live validation with sanitized details.

### Explicit Non-Goals

- Do not let the LLM answer questions.
- Do not ask the LLM for full ASTs in the main path.
- Do not include gold FOL or gold answers in prompts.
- Do not treat mocked tests as sufficient when configured live provider access is available.

### Completion Checklist

- [x] Frame extractor interface exists.
- [x] Mock extractor exists.
- [x] Configured async client exists.
- [x] Repair/retry/cache behavior is tested.
- [x] Live parse-frame smoke is passed or honestly reported as blocked.
- [x] `report.md` contains Batch 5 result.

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

- [x] Async scheduler exists.
- [x] Local/API cache modes exist.
- [x] Single-flight locks are tested.
- [x] Failure isolation works.
- [x] `report.md` contains Batch 6 result.

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

- [x] Numeric extraction exists.
- [x] Deterministic arithmetic works for required cases.
- [x] Provenance is preserved.
- [x] Anti-hardcode numeric tests pass.
- [x] `report.md` contains Batch 7 result.

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

- [x] Horn prover exists.
- [x] Safe contraposition is tested.
- [x] Quantifier behavior is bounded and tested.
- [x] Answer decision works.
- [x] `report.md` contains Batch 8 result.

## Mandatory Batch 8.5 - Numeric Layer Modularization and Maintainability

### Goal

Split the large Batch 7 numeric layer into focused modules while preserving the exact runtime contract consumed by Batch 8 and required by Batch 9.

### Why this batch exists

Batch 7 intentionally kept numeric extraction, merge logic, deterministic evaluation, routing, and orchestration in one module for fast review. After Batch 8 proves the solver handoff contract, the numeric layer should be made maintainable before Z3 and fallback logic build on top of it. This batch reduces file size and responsibility concentration without changing scoring behavior.

### Inputs / Dependencies

- Batches 1-8 outputs.
- Existing `app/numeric/` package from Batch 7.
- Batch 8 solver integration points that consume numeric facts, derived facts, proof trace steps, and Z3 constraint candidates.
- `flow.md` numeric layer and proof-trace requirements.
- `PLAN.md` numeric reasoning and maintainability requirements.

### Exact Task List

- B8.5-T1: Inventory current `app/numeric/layer.py` responsibilities and document the intended split in `report.md`.
- B8.5-T2: Keep the public numeric API stable, especially `from app.numeric import build_numeric_layer` and `NumericLayerResult`.
- B8.5-T3: Move frame, AST, and source-text extraction helpers into a focused numeric extraction module.
- B8.5-T4: Move AST/frame/source precedence, conflict detection, and supplemental comparison selection into a focused merge or resolution module.
- B8.5-T5: Move deterministic arithmetic and comparison evaluation into a focused evaluator module.
- B8.5-T6: Move Z3-compatible numeric constraint candidate construction/routing helpers into a focused routing module.
- B8.5-T7: Reduce `app/numeric/layer.py` to a thin orchestration module that wires extraction, resolution, evaluation, solver context, and result creation.
- B8.5-T8: Preserve all provenance fields, warnings, conflict traces, derived facts, and solver-context keys exactly unless a failing test proves a correction is required.
- B8.5-T9: Add or update tests that prove behavior is unchanged for numeric extraction, duplicate source-text suppression, conflict precedence, arithmetic evaluation, and Z3 candidate routing.
- B8.5-T10: Append Batch 8.5 execution details to `report.md`, including every touched file over 200 lines with line count and rationale.

### Files or Modules Likely Created or Updated

- `app/numeric/layer.py`
- `app/numeric/extractors.py`
- `app/numeric/resolution.py`
- `app/numeric/evaluator.py`
- `app/numeric/routing.py`
- `app/numeric/__init__.py`
- `tests/test_numeric_layer.py`
- Optional focused numeric test files if splitting tests improves clarity.
- `report.md`
- `task.md`

### Required Outputs / Artifacts

- Modular numeric package with focused extraction, resolution, evaluation, routing, and orchestration responsibilities.
- Stable public numeric API for pipeline and solver consumers.
- Reduced `app/numeric/layer.py` orchestration file.
- Regression coverage proving no behavior drift.
- Batch 8.5 report entry.

### Acceptance Criteria

- `app/numeric/layer.py` is reduced to thin orchestration and should be under 200 lines unless a clear rationale is reported.
- Numeric layer output shape remains compatible with Batch 8 and Batch 9 consumers.
- Existing numeric tests still pass without weakening assertions.
- Source-text supplemental extraction remains supplemental and does not duplicate authoritative AST/frame comparisons.
- No record ID, question ID, entity-list, answer-label, gold answer, `premises-FOL`, or explanation shortcut is introduced.
- Any touched file over 200 lines is reported in `report.md`.

### Required Tests or Validations

- `python -m unittest tests/test_numeric_layer.py`
- `python -m unittest tests/test_async_pipeline.py`
- `python -m unittest`
- Optional targeted import/API smoke check if module boundaries change.

### Explicit Non-Goals

- Do not add new solver capabilities beyond preserving the Batch 8 contract.
- Do not implement Batch 9 Z3 adapter, semantic fallback, or nested implication routing.
- Do not change answer decision behavior.
- Do not call the LLM or API for this refactor unless an existing smoke command explicitly requires it.
- Do not use dataset-specific examples to justify module boundaries.

### Completion Checklist

- [x] Numeric responsibilities are split into focused modules.
- [x] `app/numeric/layer.py` is a thin orchestration layer.
- [x] Public numeric imports remain stable.
- [x] Numeric behavior regression tests pass.
- [x] `report.md` contains Batch 8.5 result and file-size notes.

## Mandatory Batch 8.6 - LLM Parser Prompt Hardening and Parser Smoke Coverage

### Goal

Strengthen the premise and candidate parse-frame prompts so the configured LLM can act as the primary semantic parser for nested, numeric, rule, fact, claim, and ambiguous educational logic text without hardcoding dataset examples.

### Why this batch exists

The parser prompt is currently the most fragile root-cause point in the pipeline. Downstream symbolic reasoning can only work if the LLM emits faithful compact parse frames. This batch improves parser instructions and parser validation before broader Z3/fallback work and before larger dataset smoke runs.

### Inputs / Dependencies

- Batches 1-8.5 outputs.
- Existing `app/llm/prompts.py`, frame extractor, frame schema, compiler, and validation tests.
- `flow.md` parse-frame, numeric-frame, and runtime LLM rules.
- `PLAN.md` LLM parse-frame extraction plan.
- Existing `.env` model configuration, without exposing raw secrets.

### Exact Task List

- B8.6-T1: Audit current premise and candidate prompts against `flow.md` frame kinds, slot types, numeric requirements, nested implication preservation, ambiguity behavior, and no-answering rules.
- B8.6-T2: Expand prompt instructions for rule/fact/claim/compound/ambiguous frames without adding record-specific examples or dataset-derived answers.
- B8.6-T3: Add explicit numeric parser guidance for `numeric_value`, `numeric_condition`, `arithmetic_expression`, units, comparison phrases, percentages, GPA, scores, deadlines, durations, fees, and thresholds.
- B8.6-T4: Add prompt guidance for nested or compound natural-language premises so the model preserves implication direction and emits `compound` or `ambiguous` rather than flattening unsafely.
- B8.6-T5: Add candidate prompt guidance for MCQ options, Yes/No/Unknown claims, numeric claims, and open-ended claims while still forbidding final-answer generation.
- B8.6-T6: Add or update tests that inspect prompt text for required schema constraints, numeric guidance, no-reference-field rules, and no final-answer instruction drift.
- B8.6-T7: Add mocked parser tests for representative synthetic nested/numeric/rule/candidate frames that do not come from gold labels or record-specific examples.
- B8.6-T8: Run credential-gated live parse-frame smoke using the configured `.env` model on synthetic runtime-safe inputs; report sanitized blockers honestly if unavailable.
- B8.6-T9: Ensure prompt/cache versioning is updated when prompt content changes so stale parse-frame cache entries cannot mix with the new parser contract.
- B8.6-T10: Append Batch 8.6 execution details to `report.md`, including live smoke outcome and file-size notes.

### Files or Modules Likely Created or Updated

- `app/llm/prompts.py`
- `app/llm/extractor.py` only if prompt/cache version wiring requires it.
- `scripts/smoke_test_llm_parse_frame.py`
- `tests/test_llm_frame_extraction.py`
- Optional focused prompt tests.
- `report.md`
- `task.md`

### Required Outputs / Artifacts

- Hardened premise/candidate/repair prompts.
- Updated prompt version if prompt text changes.
- Prompt regression tests.
- Live parse-frame smoke result or sanitized blocker.
- Batch 8.6 report entry.

### Acceptance Criteria

- Prompts cover all approved frame kinds and slot types used by the runtime.
- Numeric and nested premise guidance is explicit and not keyword-only or record-specific.
- Prompts forbid final-answer generation and reference-only fields.
- Prompt/cache version changes when prompt content changes.
- Live parse-frame smoke passes with the configured model, or a sanitized blocker is reported.

### Required Tests or Validations

- `python -m unittest tests/test_llm_frame_extraction.py`
- `python scripts/smoke_test_llm_parse_frame.py --env-path .env --timeout-seconds 20 --max-attempts 3`
- `python -m unittest`

### Explicit Non-Goals

- Do not tune prompts to specific dataset records, gold FOL, gold answers, or gold explanations.
- Do not ask the LLM to solve or choose final answers.
- Do not change frame schema unless a clear validation gap is found and tests justify it.
- Do not implement Z3, fallback, public explanation rendering, or API behavior.

### Completion Checklist

- [x] Parser prompts are hardened for approved frame/slot/numeric/nested cases.
- [x] Prompt/cache versioning is updated when needed.
- [x] Prompt regression tests pass.
- [x] Live parse-frame smoke passes or a sanitized blocker is reported.
- [x] `report.md` contains Batch 8.6 result.

## Mandatory Batch 9 - Z3 Adapter, Nested Implication Routing, and Semantic Fallback

### Goal

Extend solver coverage to supported numeric/non-Horn fragments and add a confidence-capped fallback when symbolic routes cannot answer.

### Why this batch exists

Some dataset questions include arithmetic, grounded Boolean constraints, or nested implication patterns that exceed Horn reasoning. Unsupported cases must be traceable rather than silently guessed.

### Inputs / Dependencies

- Batches 1-8.6 outputs.
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

- [x] Solver router exists.
- [x] Z3 adapter handles supported fragments.
- [x] Unsupported fragments are explicit.
- [x] Semantic fallback is confidence-capped.
- [x] `report.md` contains Batch 9 result.

## Mandatory Batch 9.5 - Solver Citation Source-Text Enrichment

### Goal

Ensure every solver proof step carries enough source text and citation metadata for later public explanation rendering.

### Why this batch exists

Batch 8 solver proof steps currently preserve logical derivations and premise IDs, but public explanations need human-readable citations. Batch 9 may add Z3 and fallback routes, so citation enrichment should happen after route expansion and before explanation generation.

### Inputs / Dependencies

- Batches 1-9 outputs.
- Existing proof trace schemas and solver result models.
- Horn, quantifier, contraposition, Z3/router, and fallback outputs from earlier batches.
- `flow.md` proof-trace and explanation requirements.
- `PLAN.md` explanation grounding and debug trace requirements.

### Exact Task List

- B9.5-T1: Audit solver proof steps for missing `source_text`, premise IDs, candidate labels, and route-specific citation metadata.
- B9.5-T2: Add a deterministic source registry or citation resolver that maps premise/candidate AST metadata into proof-trace citations.
- B9.5-T3: Enrich Horn and contraposition derivations with original source text whenever available.
- B9.5-T4: Enrich numeric, Z3, unsupported-route, and semantic-fallback proof steps with source text or explicit missing-source warnings.
- B9.5-T5: Preserve secret/reference-field guards so citations cannot include `premises-FOL`, gold answers, explanations, or `idx`.
- B9.5-T6: Add tests proving solver proof steps include source text for premise-derived facts and safe candidate references for candidate-derived claims.
- B9.5-T7: Add tests proving missing citation data produces traceable warnings rather than silent empty citations.
- B9.5-T8: Append Batch 9.5 execution details to `report.md`, including file-size notes.

### Files or Modules Likely Created or Updated

- `app/tracing/`
- `app/solver/`
- `app/pipeline/runtime.py`
- `tests/test_horn_solver.py`
- `tests/test_solver_routing.py`
- Optional focused citation/proof-trace tests.
- `report.md`
- `task.md`

### Required Outputs / Artifacts

- Citation resolver or equivalent source-text enrichment path.
- Solver proof steps with source text when available.
- Warnings for missing source text.
- Regression tests for citation completeness and reference-field safety.
- Batch 9.5 report entry.

### Acceptance Criteria

- Public explanation code can read source text from proof-trace citations without re-reading runtime inputs ad hoc.
- Solver citations preserve premise ID, candidate label, route, and source text where available.
- Missing citation source text is explicit and trace-visible.
- No reference-only training annotations or secrets can enter citations.

### Required Tests or Validations

- Citation/proof-trace focused tests added in this batch.
- Relevant solver and pipeline tests.
- `python -m unittest`

### Explicit Non-Goals

- Do not generate final public explanations yet.
- Do not change entailment truth values or answer decisions.
- Do not use gold explanations as citation text.
- Do not implement API endpoint behavior.

### Completion Checklist

- [x] Solver proof citations include source text where available.
- [x] Missing source text warnings are trace-visible.
- [x] Citation safety tests pass.
- [x] Entailment and answer behavior remain unchanged.
- [x] `report.md` contains Batch 9.5 result.

## Mandatory Batch 9.6 - Proof Trace Explanation Readiness

### Goal

Make proof traces sufficiently complete, ordered, and stable for high-quality public explanation rendering in Batch 10.

### Why this batch exists

Explanation quality is a scoring dimension. Before building the public output layer, the proof trace should expose a clean reasoning chain, route labels, numeric computations, confidence signals, unsupported gaps, and citations in a renderer-friendly contract.

### Inputs / Dependencies

- Batches 1-9.5 outputs.
- Enriched solver citations from Batch 9.5.
- Numeric derivations, Horn derivations, Z3/fallback route metadata, and answer-decision traces.
- `flow.md` proof trace, answer decision, and explanation-generation sections.
- `PLAN.md` proof-trace explanation requirements.

### Exact Task List

- B9.6-T1: Define an explanation-ready proof-trace contract or helper view that orders premise facts, derived facts, numeric computations, solver route steps, and final decision.
- B9.6-T2: Ensure proof-trace steps have stable IDs, route labels, statuses, used premise IDs, derived fact strings, citations, warnings, and optional confidence metadata.
- B9.6-T3: Add route-specific trace details for Horn, contraposition, quantifier instantiation, Z3, fallback, and capability gaps.
- B9.6-T4: Add numeric explanation fields for computed values, units, expressions, and source citations.
- B9.6-T5: Add answer-decision trace details showing claim result, negated-claim result, MCQ candidate outcomes, and why `Unknown` was selected when applicable.
- B9.6-T6: Add tests that convert representative traces into explanation-ready structures without missing required fields.
- B9.6-T7: Add tests that proof traces remain runtime-safe and do not contain reference-only fields.
- B9.6-T8: Append Batch 9.6 execution details to `report.md`, including file-size notes.

### Files or Modules Likely Created or Updated

- `app/tracing/`
- `app/pipeline/runtime.py`
- `app/output/` only for proof-trace view models/helpers, not final public formatting.
- `tests/test_debug_trace.py`
- Optional proof-trace readiness tests.
- `report.md`
- `task.md`

### Required Outputs / Artifacts

- Explanation-ready proof-trace contract/helper.
- Tests for ordering, required fields, route metadata, numeric derivations, decision details, and runtime safety.
- Batch 9.6 report entry.

### Acceptance Criteria

- Batch 10 can render public explanations from proof traces without inventing reasoning.
- Proof traces include enough structured evidence for numeric, symbolic, fallback, and `Unknown` cases.
- Trace ordering is deterministic.
- Reference-only and secret-safety guards still pass.

### Required Tests or Validations

- Proof-trace readiness tests added in this batch.
- `python -m unittest tests/test_debug_trace.py`
- `python -m unittest`

### Explicit Non-Goals

- Do not produce final public response formatting.
- Do not add MCQ forced-choice submission policy.
- Do not call an LLM to verbalize explanations.
- Do not change solver truth values.

### Completion Checklist

- [x] Explanation-ready proof-trace contract exists.
- [x] Route, numeric, citation, and decision details are represented.
- [x] Trace ordering is deterministic.
- [x] Runtime safety tests pass.
- [x] `report.md` contains Batch 9.6 result.

## Mandatory Batch 9.7 - Parser/AST Canonicalization and Entailment Smoke Hardening

### Goal

Reduce avoidable `Unknown` outputs caused by LLM parse-frame drift, predicate/entity mismatch, and subject/object loss before public explanation formatting is built.

### Why this batch exists

Live two-record smoke after Batch 9.6 reached the solver but returned `Unknown` for every sample. The trace showed two root issues: semantically related phrases compiled into incompatible predicates/entities, and some factual relations lost their subject/object structure. Batch 10 is explicitly forbidden from changing solver truth values, so parser/AST canonicalization must be hardened before explanations and submission adapters are added.

### Inputs / Dependencies

- Batches 1-9.6 outputs.
- Existing LLM parse-frame extractor, prompts, frame schema, compiler, AST validation, normalization, Horn solver, router, proof-trace readiness helpers, and debug traces.
- `flow.md` sections on parse frames, frame-to-AST compilation, AST validation/normalization, solver routing, and debug trace root-cause reporting.
- `PLAN.md` predicate mismatch mitigation: per-premise-bundle predicate map, arity checks, and phrase alias tracking.
- Recent smoke artifacts may be used only as diagnostic evidence; runtime code must still use only `premises-NL` and `question`.

### Exact Task List

- B9.7-T1: Reproduce or inspect the current two-record LLM smoke traces and summarize the exact parser/AST root causes in `report.md`.
- B9.7-T2: Audit premise and candidate frames after LLM extraction and deterministic compilation for entity drift, predicate drift, arity mismatch, generic class phrase mismatch, and subject/object loss.
- B9.7-T3: Implement bundle-local predicate/entity canonicalization derived only from current runtime source text, validated frames, and compiled AST metadata.
- B9.7-T4: Preserve source metadata while aligning singular/plural class phrases, named instances, and compatible role/domain phrases within the same premise bundle.
- B9.7-T5: Harden frame compilation or normalization so relation-like facts keep their meaningful subject and object arguments instead of collapsing into argumentless or wrong-subject predicates.
- B9.7-T6: Ensure Horn, bounded quantifier, safe contraposition, and router paths consume the canonicalized AST consistently without changing proof citations or source-text provenance.
- B9.7-T7: Add synthetic, non-dataset-specific tests for multi-step educational eligibility chains, generic project/code rule chains, predicate/entity aliasing, and subject/object preservation.
- B9.7-T8: Add anti-overfit tests proving canonicalization does not depend on `record_id`, `sample_id`, `question_id`, option label, gold answer, gold explanation, `idx`, or `premises-FOL`.
- B9.7-T9: Run the live `.env` two-record LLM smoke with `--max-concurrency 2` after the fix, compare against the previous all-`Unknown` trace, and report whether remaining `Unknown` outputs are due to parser, compiler, solver capability, or provider instability.
- B9.7-T10: Append Batch 9.7 execution details to `report.md`, including file-size notes and any remaining root-cause risks.

### Files or Modules Likely Created or Updated

- `app/logic/normalization/`
- `app/logic/compiler/`
- `app/logic/validation/`
- `app/llm/prompts.py` if prompt guidance is needed to preserve relation arguments.
- `app/solver/horn/` only if canonicalized AST consumption needs a small compatibility fix.
- `app/pipeline/runtime.py` only if trace metadata must expose canonicalization diagnostics.
- `tests/test_logic_ast.py`
- `tests/test_frame_compiler.py`
- Optional focused canonicalization tests.
- `report.md`
- `task.md`

### Required Outputs / Artifacts

- Bundle-local predicate/entity canonicalization or alias-map behavior.
- Subject/object preserving compilation or normalization for relation-like facts.
- Trace-visible canonicalization diagnostics or warnings when alignment is applied or rejected.
- Regression tests for chain entailment, aliasing, subject/object preservation, and anti-overfit boundaries.
- Updated two-record smoke artifacts or a documented provider blocker.
- Batch 9.7 report entry.

### Acceptance Criteria

- Synthetic chain tests prove that semantically equivalent premise/candidate phrasing can entail the expected claim without using dataset-specific mappings.
- Relation-like facts preserve enough argument structure for downstream Horn/quantifier reasoning.
- Canonicalization is bundle-local, deterministic, trace-visible, and source-cited.
- No runtime path reads or depends on `premises-FOL`, `answer`, `explanation`, `idx`, record IDs, sample IDs, question IDs, or option labels for entailment.
- The two-record LLM smoke no longer fails as all-`Unknown` solely because of parser/AST subject/object loss or predicate/entity drift; if provider instability or a deeper solver gap remains, the exact sanitized root cause is reported.

### Required Tests or Validations

- Focused canonicalization/compiler tests added in this batch.
- `python -m unittest tests/test_frame_compiler.py tests/test_logic_ast.py`
- Relevant solver tests, especially Horn, quantifier, routing, and answer decision tests.
- `python -m unittest`
- Live smoke using `scripts/evaluate_local.py` on the existing two-record smoke input with `.env`, `--max-concurrency 2`, bounded timeouts, and sanitized artifacts.

### Explicit Non-Goals

- Do not hardcode dataset record IDs, sample IDs, answer labels, entities, predicates, gold explanations, gold FOL strings, or observed correct answers.
- Do not use `premises-FOL`, `answer`, `explanation`, or `idx` in runtime prompts, compiler inputs, solver inputs, traces, or predictions.
- Do not make the LLM produce final answers or full formal ASTs.
- Do not change public explanation formatting, API behavior, scoring scripts, or official MCQ forced-choice policy.
- Do not weaken solver soundness to avoid `Unknown`; unsupported cases must still report `solver_capability_gap`.

### Completion Checklist

- [x] Parser/AST root cause from the all-`Unknown` smoke is documented.
- [x] Bundle-local canonicalization exists and is tested.
- [x] Relation subject/object preservation is tested.
- [x] Anti-overfit/leakage tests pass.
- [x] Two-record live LLM smoke is rerun and reported.
- [x] `report.md` contains Batch 9.7 result.

## Mandatory Batch 10 - Explanation Generation, Open-Ended Output, and MCQ Submission Adapter

### Goal

Produce public-facing answers and explanations from proof traces, including configurable MCQ submission behavior and best-effort open-ended handling.

### Why this batch exists

The competition requires `answer` and `explanation`. These outputs must be grounded in proof traces, not free-form LLM reasoning.

### Inputs / Dependencies

- Batches 1-9.7 outputs.
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

- Batches 1-12 outputs, including mandatory fractional batches 8.5, 8.6, 9.5, and 9.6.
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

- This track is outside the mandatory batch dependency chain.
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
- Batch 8 -> Batch 8.5: core symbolic solver before numeric layer refactor, so the refactor preserves a proven solver handoff contract.
- Batch 8.5 -> Batch 8.6: maintainable numeric modules before prompt hardening and larger downstream smoke work.
- Batch 8.6 -> Batch 9: hardened parser prompts before Z3/fallback extensions rely on parsed numeric and logic structure.
- Batch 9 -> Batch 9.5: complete solver routes before enriching route-specific source-text citations.
- Batch 9.5 -> Batch 9.6: source-text citations before building explanation-ready proof-trace views.
- Batch 9.6 -> Batch 9.7: explanation-ready traces expose enough root-cause detail to harden parser/AST canonicalization before output formatting.
- Batch 9.7 -> Batch 10: canonicalized parser/AST handoff reduces avoidable `Unknown` answers before public explanations and adapters.
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
- [ ] LLM parser prompts are schema-grounded, numeric-aware, nested-premise-aware, and tested without reference-field leakage.
- [ ] Bundle-local predicate/entity canonicalization preserves relation arguments and reduces avoidable `Unknown` outputs without record-specific maps.
- [ ] Numeric layer tracks source provenance and inserts derived facts into proof trace.
- [ ] Horn prover supports tested safe contraposition.
- [ ] Quantifier handling supports schema-level universal matching, bounded instantiation, and unsupported-case reporting.
- [ ] Nested implications are routed to grounded Z3 encoding or explicit `solver_capability_gap`.
- [ ] Semantic fallback exists, is confidence-capped, and does not override symbolic proofs.
- [ ] Solver proof citations preserve source text where available and report missing citation data explicitly.
- [ ] Proof traces are explanation-ready before public output formatting.
- [ ] MCQ local `Unknown` and official submission adapter behavior are tested separately.
- [ ] Best-effort open-ended answers are proof-grounded or return `Unknown`.
- [ ] Explanations are generated from proof traces only.
- [ ] Debug traces identify root causes without leaking secrets.
- [ ] Model configuration uses `.env` as source of truth and documents `SHOPAIKEY_MODEL` without exposing the API key.
- [ ] Early live LLM connectivity smoke has passed or is documented as blocked with sanitized details.
- [ ] Live parse-frame smoke has passed once the extractor exists, or is documented as blocked with sanitized details.
- [ ] Evaluation scripts score predictions only outside runtime.
- [ ] NO DATA OVERFITTING: no record-specific tuning, answer leakage, gold-FOL leakage, or dataset-row shortcuts.
- [ ] NO HARDCODING: no hardcoded answers, entity lists, predicate maps, numeric thresholds, or record-specific rule branches.
- [ ] Every touched file over 200 lines is reported in `report.md` with line count and rationale.
- [ ] `report.md` has a detailed entry for every completed batch.

## Progress Tracker

### Batches

- [x] Batch 1 - Foundation, Config, and Runtime-Safe Data Layer
- [x] Batch 2 - Cache Keys, Candidate Extraction, and Question Typing
- [x] Batch 3 - Parse Frame, Typed AST Schema, Compilation, Validation, and Normalization
- [x] Batch 4 - Debug Trace and Proof Trace Infrastructure
- [x] Batch 5 - LLM Parse-Frame Extractor with Mockable Runtime
- [x] Batch 6 - Async Pipeline, Premise Cache, and Single-Flight Locks
- [x] Batch 7 - Numeric Layer with Source Provenance
- [x] Batch 8 - Horn Prover, Contraposition, Quantifier Instantiation, and Entailment Decision
- [x] Batch 8.5 - Numeric Layer Modularization and Maintainability
- [x] Batch 8.6 - LLM Parser Prompt Hardening and Parser Smoke Coverage
- [x] Batch 9 - Z3 Adapter, Nested Implication Routing, and Semantic Fallback
- [x] Batch 9.5 - Solver Citation Source-Text Enrichment
- [x] Batch 9.6 - Proof Trace Explanation Readiness
- [ ] Batch 9.7 - Parser/AST Canonicalization and Entailment Smoke Hardening
- [ ] Batch 10 - Explanation Generation, Open-Ended Output, and MCQ Submission Adapter
- [ ] Batch 11 - API Endpoint
- [ ] Batch 12 - Evaluation, Scoring, and Error Analysis
- [ ] Batch 13 - Regression Suite and Final Hardening

### Milestones

- [x] M1 - Runtime-Safe Foundation
- [x] M2 - Query Contract
- [x] M3 - Logic Representation Contract
- [x] M4 - Observability Foundation
- [x] M5 - LLM Semantic Parser
- [x] M6 - Async Runtime Skeleton
- [x] M7 - Numeric Reasoning Layer
- [x] M8 - Core Symbolic Reasoning
- [x] M8.5 - Numeric Layer Maintainability
- [x] M8.6 - LLM Parser Prompt Hardening
- [x] M9 - Extended Verification
- [x] M9.5 - Solver Citation Enrichment
- [x] M9.6 - Proof Trace Explanation Readiness
- [ ] M9.7 - Parser/AST Canonicalization Hardening
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
- [x] B3-T1
- [x] B3-T2
- [x] B3-T3
- [x] B3-T4
- [x] B3-T5
- [x] B3-T6
- [x] B3-T7
- [x] B3-T8
- [x] B3-T9
- [x] B3-T10
- [x] B3-T11
- [x] B4-T1
- [x] B4-T2
- [x] B4-T3
- [x] B4-T4
- [x] B4-T5
- [x] B4-T6
- [x] B4-T7
- [x] B4-T8
- [x] B4-T9
- [x] B5-T1
- [x] B5-T2
- [x] B5-T3
- [x] B5-T4
- [x] B5-T5
- [x] B5-T6
- [x] B5-T7
- [x] B5-T8
- [x] B5-T9
- [x] B5-T10
- [x] B5-T11
- [x] B5-T12
- [x] B6-T1
- [x] B6-T2
- [x] B6-T3
- [x] B6-T4
- [x] B6-T5
- [x] B6-T6
- [x] B6-T7
- [x] B6-T8
- [x] B6-T9
- [x] B6-T10
- [x] B6-T11
- [x] B7-T1
- [x] B7-T2
- [x] B7-T3
- [x] B7-T4
- [x] B7-T5
- [x] B7-T6
- [x] B7-T7
- [x] B7-T8
- [x] B7-T9
- [x] B7-T10
- [x] B7-T11
- [x] B8-T1
- [x] B8-T2
- [x] B8-T3
- [x] B8-T4
- [x] B8-T5
- [x] B8-T6
- [x] B8-T7
- [x] B8-T8
- [x] B8-T9
- [x] B8-T10
- [x] B8-T11
- [x] B8-T12
- [x] B8-T13
- [x] B8.5-T1
- [x] B8.5-T2
- [x] B8.5-T3
- [x] B8.5-T4
- [x] B8.5-T5
- [x] B8.5-T6
- [x] B8.5-T7
- [x] B8.5-T8
- [x] B8.5-T9
- [x] B8.5-T10
- [x] B8.6-T1
- [x] B8.6-T2
- [x] B8.6-T3
- [x] B8.6-T4
- [x] B8.6-T5
- [x] B8.6-T6
- [x] B8.6-T7
- [x] B8.6-T8
- [x] B8.6-T9
- [x] B8.6-T10
- [x] B9-T1
- [x] B9-T2
- [x] B9-T3
- [x] B9-T4
- [x] B9-T5
- [x] B9-T6
- [x] B9-T7
- [x] B9-T8
- [x] B9-T9
- [x] B9-T10
- [x] B9-T11
- [x] B9.5-T1
- [x] B9.5-T2
- [x] B9.5-T3
- [x] B9.5-T4
- [x] B9.5-T5
- [x] B9.5-T6
- [x] B9.5-T7
- [x] B9.5-T8
- [x] B9.6-T1
- [x] B9.6-T2
- [x] B9.6-T3
- [x] B9.6-T4
- [x] B9.6-T5
- [x] B9.6-T6
- [x] B9.6-T7
- [x] B9.6-T8
- [x] B9.7-T1
- [x] B9.7-T2
- [x] B9.7-T3
- [x] B9.7-T4
- [x] B9.7-T5
- [x] B9.7-T6
- [x] B9.7-T7
- [x] B9.7-T8
- [ ] B9.7-T9
- [x] B9.7-T10
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
