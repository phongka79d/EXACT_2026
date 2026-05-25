"""Async orchestration for local and API-style runtime requests."""

from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, Sequence

from app.cache import build_api_premise_cache_key, build_local_premise_cache_key
from app.data import LocalRuntimeSample, RuntimeQuery
from app.llm import FrameExtractionError, FrameExtractionInput
from app.llm.extractor import FrameExtractor
from app.logic.ast import LogicNode, NotNode
from app.logic.compiler import compile_frame_to_ast
from app.logic.frames import ParseFrame
from app.numeric import NumericLayerResult, build_numeric_layer
from app.output.decision import CandidateEntailment, decide_answer
from app.questions import extract_candidates
from app.solver import SolverRequest, prove_entailment
from app.tracing import CacheMetadata, DebugTrace, NumericDerivation, ProofTraceStep, SourceCitation, TraceStage

from .models import PipelineSampleResult


@dataclass(frozen=True)
class _SampleContext:
    cache_mode: Literal["local", "api"]
    sample_id: str | None
    record_id: int | None
    question_id: int | None
    premises_nl: list[str]
    question: str


@dataclass(frozen=True)
class _PremiseBundle:
    frames: list[ParseFrame]
    asts: list[LogicNode]


class _RequestTimeoutError(TimeoutError):
    pass


class AsyncRuntimePipeline:
    """Async runtime pipeline from parse-frame extraction through symbolic answer decision."""

    def __init__(
        self,
        *,
        frame_extractor: FrameExtractor,
        max_concurrency: int = 8,
        request_timeout_seconds: float = 20.0,
        sample_timeout_seconds: float = 60.0,
        api_hash_components: Sequence[str] = (),
    ) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be >= 1")
        if request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds must be > 0")
        if sample_timeout_seconds <= 0:
            raise ValueError("sample_timeout_seconds must be > 0")
        self._frame_extractor = frame_extractor
        self._max_concurrency = max_concurrency
        self._request_timeout_seconds = request_timeout_seconds
        self._sample_timeout_seconds = sample_timeout_seconds
        self._api_hash_components = tuple(api_hash_components)
        self._premise_cache: dict[str, _PremiseBundle] = {}
        self._single_flight_locks: dict[str, asyncio.Lock] = {}
        self._premise_conversion_counts: dict[str, int] = {}

    @property
    def premise_conversion_counts(self) -> dict[str, int]:
        return dict(self._premise_conversion_counts)

    async def process_local_samples(self, samples: Sequence[LocalRuntimeSample]) -> list[PipelineSampleResult]:
        semaphore = asyncio.Semaphore(self._max_concurrency)

        async def run_one(sample: LocalRuntimeSample) -> PipelineSampleResult:
            async with semaphore:
                context = _SampleContext(
                    cache_mode="local",
                    sample_id=sample.sample_id,
                    record_id=sample.record_id,
                    question_id=sample.question_id,
                    premises_nl=list(sample.premises_nl),
                    question=sample.question,
                )
                return await self._process_context(context)

        results = await asyncio.gather(*(run_one(sample) for sample in samples))
        return sorted(results, key=lambda item: ((item.record_id if item.record_id is not None else -1), (item.question_id if item.question_id is not None else -1)))

    async def process_runtime_query(self, query: RuntimeQuery) -> PipelineSampleResult:
        context = _SampleContext(
            cache_mode="api",
            sample_id=None,
            record_id=None,
            question_id=None,
            premises_nl=list(query.premises_nl),
            question=query.question,
        )
        return await self._process_context(context)

    async def _process_context(self, context: _SampleContext) -> PipelineSampleResult:
        started_at = time.perf_counter()
        try:
            return await asyncio.wait_for(self._process_context_inner(context, started_at), timeout=self._sample_timeout_seconds)
        except asyncio.TimeoutError:
            return self._build_failure_result(
                context,
                started_at=started_at,
                root_cause_category="timeout_error",
                root_cause_message=f"Sample processing timed out after {self._sample_timeout_seconds:.3f}s",
                stage_name="sample_timeout",
                cache_mode=context.cache_mode,
                cache_key=None,
                cache_hit=None,
                single_flight_waited=None,
                question_type=None,
            )
        except Exception as exc:  # pragma: no cover - defensive failure isolation
            return self._build_failure_result(
                context,
                started_at=started_at,
                root_cause_category="api_error",
                root_cause_message=str(exc),
                stage_name="unexpected_error",
                cache_mode=context.cache_mode,
                cache_key=None,
                cache_hit=None,
                single_flight_waited=None,
                question_type=None,
            )

    async def _process_context_inner(self, context: _SampleContext, started_at: float) -> PipelineSampleResult:
        stages: list[TraceStage] = []

        candidate_result, candidate_stage = self._extract_candidates(context.question)
        stages.append(candidate_stage)
        if candidate_stage.status == "failed":
            return self._build_failure_result(
                context,
                started_at=started_at,
                root_cause_category="candidate_extraction_error",
                root_cause_message=candidate_stage.warnings[0] if candidate_stage.warnings else "Candidate extraction failed",
                stage_name="candidate_extraction",
                cache_mode=context.cache_mode,
                cache_key=None,
                cache_hit=None,
                single_flight_waited=None,
                question_type=None,
                stages=stages,
            )

        cache_key = self._build_cache_key(context)
        premise_bundle, cache_hit, single_flight_waited, premise_stage = await self._load_premises(cache_key, context.premises_nl)
        stages.append(premise_stage)
        if premise_stage.status == "failed":
            category = "timeout_error" if premise_stage.name == "premise_timeout" else "llm_frame_error"
            message = premise_stage.warnings[0] if premise_stage.warnings else "Premise conversion failed"
            return self._build_failure_result(
                context,
                started_at=started_at,
                root_cause_category=category,
                root_cause_message=message,
                stage_name=premise_stage.name,
                cache_mode=context.cache_mode,
                cache_key=cache_key,
                cache_hit=cache_hit,
                single_flight_waited=single_flight_waited,
                question_type=candidate_result.question_type,
                stages=stages,
            )

        candidate_asts, candidate_stage = await self._compile_candidate_claims(candidate_result)
        stages.append(candidate_stage)
        if candidate_stage.status == "failed":
            category = "timeout_error" if candidate_stage.name == "candidate_timeout" else "llm_frame_error"
            message = candidate_stage.warnings[0] if candidate_stage.warnings else "Candidate conversion failed"
            return self._build_failure_result(
                context,
                started_at=started_at,
                root_cause_category=category,
                root_cause_message=message,
                stage_name=candidate_stage.name,
                cache_mode=context.cache_mode,
                cache_key=cache_key,
                cache_hit=cache_hit,
                single_flight_waited=single_flight_waited,
                question_type=candidate_result.question_type,
                stages=stages,
            )

        numeric_result, numeric_stage = self._run_numeric_layer(premise_bundle, candidate_asts)
        stages.append(numeric_stage)
        if numeric_stage.status == "failed" or numeric_result is None:
            message = numeric_stage.warnings[0] if numeric_stage.warnings else "Numeric layer failed"
            return self._build_failure_result(
                context,
                started_at=started_at,
                root_cause_category="numeric_extraction_error",
                root_cause_message=message,
                stage_name="numeric_layer",
                cache_mode=context.cache_mode,
                cache_key=cache_key,
                cache_hit=cache_hit,
                single_flight_waited=single_flight_waited,
                question_type=candidate_result.question_type,
                stages=stages,
            )

        entailments, solver_stage = self._run_symbolic_solver(
            premise_bundle.asts,
            candidate_result,
            candidate_asts,
            numeric_result=numeric_result,
            premises_nl=context.premises_nl,
        )
        stages.append(solver_stage)
        if solver_stage.status == "failed":
            message = solver_stage.warnings[0] if solver_stage.warnings else "Symbolic solver failed"
            return self._build_failure_result(
                context,
                started_at=started_at,
                root_cause_category="proof_search_error",
                root_cause_message=message,
                stage_name="symbolic_solver",
                cache_mode=context.cache_mode,
                cache_key=cache_key,
                cache_hit=cache_hit,
                single_flight_waited=single_flight_waited,
                question_type=candidate_result.question_type,
                stages=stages,
            )

        decision_stage_start = time.perf_counter()
        decision_result = decide_answer(candidate_result.question_type, entailments)
        decision_stage = TraceStage(
            name="answer_decision",
            status="ok" if decision_result.status == "ok" else "partial",
            duration_ms=_elapsed_ms(decision_stage_start),
            warnings=list(decision_result.warnings),
            metadata={
                "question_type": candidate_result.question_type,
                "selected_output_label": decision_result.answer,
                "used_premise_ids": decision_result.used_premise_ids,
            },
        )
        stages.append(decision_stage)

        trace_status: Literal["ok", "partial"] = "ok"
        root_cause_category: str | None = None
        root_cause_message: str | None = None
        if any(stage.status == "partial" for stage in stages):
            trace_status = "partial"
            if solver_stage.status == "partial":
                root_cause_category = "solver_capability_gap"
                root_cause_message = "Symbolic reasoning completed with capability gaps."

        total_ms = _elapsed_ms(started_at)
        trace = DebugTrace(
            sample_id=context.sample_id,
            record_id=context.record_id,
            question_id=context.question_id,
            status=trace_status,
            root_cause_category=root_cause_category,
            root_cause_message=root_cause_message,
            created_at=_utc_now_iso(),
            total_duration_ms=total_ms,
            premises_hash=_cache_key_digest(cache_key),
            warnings=[*candidate_result.warnings, *decision_result.warnings],
            stages=stages,
            cache=CacheMetadata(
                mode=context.cache_mode,
                cache_key=cache_key,
                cache_key_hash=_cache_key_digest(cache_key),
                cache_hit=cache_hit,
                single_flight_waited=single_flight_waited,
            ),
            proof_trace=[
                self._build_numeric_proof_step(numeric_result),
                *self._build_solver_proof_steps(entailments),
                self._build_decision_proof_step(candidate_result.question_type, decision_result.answer, decision_result),
            ],
            metadata={
                "question_type": candidate_result.question_type,
                "candidate_count": len(candidate_result.candidates),
                "numeric_fact_count": len(numeric_result.solver_context.get("numeric_facts", [])),
                "z3_constraint_count": len(numeric_result.z3_constraints),
                "solver_route": solver_stage.metadata.get("primary_route", "horn"),
            },
        )
        return PipelineSampleResult(
            sample_id=context.sample_id,
            record_id=context.record_id,
            question_id=context.question_id,
            answer=decision_result.answer,
            explanation=decision_result.explanation,
            status=trace_status,
            question_type=candidate_result.question_type,
            cache_mode=context.cache_mode,
            cache_key=cache_key,
            cache_hit=cache_hit,
            single_flight_waited=single_flight_waited,
            solver_handoff_ready=True,
            error=None,
            trace=trace,
        )

    def _run_numeric_layer(self, premise_bundle: _PremiseBundle, candidate_asts: Sequence[LogicNode]) -> tuple[NumericLayerResult | None, TraceStage]:
        stage_start = time.perf_counter()
        try:
            result = build_numeric_layer(
                premise_frames=premise_bundle.frames,
                premise_asts=premise_bundle.asts,
                candidate_asts=list(candidate_asts),
            )
        except Exception as exc:  # pragma: no cover - defensive protection around new stage
            return None, TraceStage(
                name="numeric_layer",
                status="failed",
                duration_ms=_elapsed_ms(stage_start),
                warnings=[str(exc)],
                metadata={},
            )

        stage_status: Literal["ok", "partial", "failed"] = "ok"
        if result.z3_constraints or result.conflicts or result.warnings:
            stage_status = "partial"
        return result, TraceStage(
            name="numeric_layer",
            status=stage_status,
            duration_ms=_elapsed_ms(stage_start),
            warnings=list(result.warnings),
            metadata={
                "frame_quantity_count": len(result.frame_quantities),
                "ast_quantity_count": len(result.ast_quantities),
                "supplemental_quantity_count": len(result.supplemental_quantities),
                "comparison_count": len(result.comparisons),
                "derived_fact_count": len(result.derived_facts),
                "z3_constraint_count": len(result.z3_constraints),
                "conflict_count": len(result.conflicts),
            },
        )

    def _build_numeric_proof_step(self, numeric_result: NumericLayerResult) -> ProofTraceStep:
        numeric_derivations: list[NumericDerivation] = []
        citations: list[SourceCitation] = []
        seen_citations: set[tuple[str, int | None, str | None]] = set()

        for fact in numeric_result.derived_facts:
            sources: list[SourceCitation] = []
            for source in fact.sources:
                citation = SourceCitation(
                    source_id=source.source_id,
                    source_text=source.source_text,
                    premise_id=source.premise_id,
                    candidate_label=source.candidate_label,
                )
                key = (citation.source_id, citation.premise_id, citation.candidate_label)
                if key not in seen_citations:
                    seen_citations.add(key)
                    citations.append(citation)
                sources.append(citation)
            rendered_value: float | int | str = fact.value
            if isinstance(fact.value, bool):
                rendered_value = str(fact.value).lower()
            numeric_derivations.append(
                NumericDerivation(
                    name=fact.name,
                    value=rendered_value,
                    unit=fact.unit,
                    expression=fact.expression,
                    sources=sources,
                )
            )

        proof_status: Literal["ok", "failed", "partial"] = "ok"
        if numeric_result.z3_constraints or numeric_result.conflicts or numeric_result.warnings:
            proof_status = "partial"

        return ProofTraceStep(
            step_id="numeric_layer",
            action="extract_evaluate_numeric_facts",
            solver_route="numeric",
            status=proof_status,
            used_premise_ids=sorted(
                {
                    source.premise_id
                    for fact in numeric_result.derived_facts
                    for source in fact.sources
                    if source.premise_id is not None
                }
            ),
            derived_facts=[fact.expression for fact in numeric_result.derived_facts],
            numeric_derivations=numeric_derivations,
            citations=citations,
            warnings=list(numeric_result.warnings),
            metadata={
                "comparison_count": len(numeric_result.comparisons),
                "z3_constraint_count": len(numeric_result.z3_constraints),
                "conflict_count": len(numeric_result.conflicts),
            },
        )

    def _run_symbolic_solver(self, premise_asts, candidate_result, candidate_asts, *, numeric_result: NumericLayerResult, premises_nl: Sequence[str]):
        stage_start = time.perf_counter()
        entailments: list[CandidateEntailment] = []
        warnings: list[str] = []
        route_counts: dict[str, int] = {}
        z3_statuses: set[str] = set()
        fallback_used_count = 0
        confidence_penalties: list[float] = []
        try:
            for candidate, candidate_ast in zip(candidate_result.candidates, candidate_asts, strict=True):
                claim_result = prove_entailment(
                    SolverRequest(
                        premise_asts=premise_asts,
                        claim_ast=candidate_ast,
                        numeric_context=numeric_result.solver_context,
                        premises_nl=premises_nl,
                        candidate_text=candidate.text,
                    )
                )
                negated_claim = _negate_claim(candidate_ast)
                negated_result = prove_entailment(
                    SolverRequest(
                        premise_asts=premise_asts,
                        claim_ast=negated_claim,
                        numeric_context=numeric_result.solver_context,
                        premises_nl=premises_nl,
                        candidate_text=f"not ({candidate.text})",
                    )
                )
                entailments.append(
                    CandidateEntailment(
                        label=candidate.label,
                        question_type=candidate.question_type,
                        claim_result=claim_result,
                        negated_claim_result=negated_result,
                    )
                )
                warnings.extend(claim_result.warnings)
                warnings.extend(claim_result.unsupported_features)
                warnings.extend(negated_result.warnings)
                warnings.extend(negated_result.unsupported_features)
                for result in (claim_result, negated_result):
                    route_counts[result.route] = route_counts.get(result.route, 0) + 1
                    z3_status = result.solver_metadata.get("z3_status")
                    if isinstance(z3_status, str) and z3_status:
                        z3_statuses.add(z3_status)
                    if bool(result.solver_metadata.get("fallback_used")):
                        fallback_used_count += 1
                    if result.confidence_penalty > 0:
                        confidence_penalties.append(result.confidence_penalty)
        except Exception as exc:
            return [], TraceStage(
                name="symbolic_solver",
                status="failed",
                duration_ms=_elapsed_ms(stage_start),
                warnings=[str(exc)],
                metadata={},
            )

        stage_status: Literal["ok", "partial"] = "ok"
        if any(item.claim_result.status != "ok" or item.negated_claim_result.status != "ok" for item in entailments):
            stage_status = "partial"
        primary_route = "mixed"
        if route_counts:
            primary_route = sorted(route_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
        return entailments, TraceStage(
            name="symbolic_solver",
            status=stage_status,
            duration_ms=_elapsed_ms(stage_start),
            warnings=_unique_strings(warnings),
            metadata={
                "candidate_count": len(entailments),
                "question_type": candidate_result.question_type,
                "route_counts": route_counts,
                "primary_route": primary_route,
                "z3_statuses": sorted(z3_statuses),
                "fallback_used_count": fallback_used_count,
                "confidence_penalties": confidence_penalties,
            },
        )

    def _build_solver_proof_steps(self, entailments: Sequence[CandidateEntailment]) -> list[ProofTraceStep]:
        steps: list[ProofTraceStep] = []
        for entailment in entailments:
            claim_step = self._build_single_solver_step(
                step_id=f"solver_claim_{entailment.label}",
                action="prove_claim",
                result=entailment.claim_result,
                candidate_label=entailment.label,
            )
            negated_step = self._build_single_solver_step(
                step_id=f"solver_negated_claim_{entailment.label}",
                action="prove_negated_claim",
                result=entailment.negated_claim_result,
                candidate_label=entailment.label,
            )
            steps.extend([claim_step, negated_step])
        return steps

    def _build_single_solver_step(self, *, step_id: str, action: str, result, candidate_label: str) -> ProofTraceStep:
        citations: list[SourceCitation] = []
        seen: set[tuple[str, int | None, str | None]] = set()
        derived_strings: list[str] = []
        for derivation in result.derived_facts:
            rendered = derivation.literal.render()
            if derivation.rule_text:
                rendered = f"{rendered} [{derivation.rule_text}]"
            derived_strings.append(rendered)
            source_id = derivation.literal.source_id or f"candidate_{candidate_label}"
            key = (source_id, derivation.literal.premise_id, candidate_label)
            if key in seen:
                continue
            seen.add(key)
            citations.append(
                SourceCitation(
                    source_id=source_id,
                    source_text=None,
                    premise_id=derivation.literal.premise_id,
                    candidate_label=candidate_label,
                )
            )

        status: Literal["ok", "partial"] = "ok"
        warnings = [*result.warnings, *result.unsupported_features]
        if result.status != "ok":
            status = "partial"
        return ProofTraceStep(
            step_id=step_id,
            action=action,
            solver_route=result.route,
            status=status,
            used_premise_ids=result.used_premise_ids,
            derived_facts=derived_strings,
            citations=citations,
            warnings=_unique_strings(warnings),
            metadata={
                "candidate_label": candidate_label,
                "entailed": result.entailed,
                "confidence": result.confidence,
                "confidence_penalty": result.confidence_penalty,
                "z3_status": result.solver_metadata.get("z3_status"),
                "fallback_used": bool(result.solver_metadata.get("fallback_used")),
                "original_route": result.solver_metadata.get("original_route"),
            },
        )

    def _build_decision_proof_step(self, question_type: str, answer: str, decision_result) -> ProofTraceStep:
        return ProofTraceStep(
            step_id="answer_decision",
            action="select_public_answer",
            solver_route="decision",
            status="ok" if decision_result.status == "ok" else "partial",
            used_premise_ids=decision_result.used_premise_ids,
            derived_facts=[f"answer={answer}"],
            warnings=list(decision_result.warnings),
            metadata={"question_type": question_type},
        )

    def _extract_candidates(self, question: str):
        stage_start = time.perf_counter()
        try:
            result = extract_candidates(question)
            stage = TraceStage(
                name="candidate_extraction",
                status="ok",
                duration_ms=_elapsed_ms(stage_start),
                warnings=list(result.warnings),
                metadata={"question_type": result.question_type, "candidate_count": len(result.candidates)},
            )
            return result, stage
        except Exception as exc:
            stage = TraceStage(
                name="candidate_extraction",
                status="failed",
                duration_ms=_elapsed_ms(stage_start),
                warnings=[str(exc)],
                metadata={},
            )
            return None, stage

    def _build_cache_key(self, context: _SampleContext) -> str:
        if context.cache_mode == "local":
            assert context.record_id is not None
            return build_local_premise_cache_key(context.record_id)
        return build_api_premise_cache_key(context.premises_nl, hash_components=self._api_hash_components)

    async def _load_premises(self, cache_key: str, premises_nl: list[str]) -> tuple[_PremiseBundle, bool, bool, TraceStage]:
        stage_start = time.perf_counter()
        existing = self._premise_cache.get(cache_key)
        if existing is not None:
            return existing, True, False, TraceStage(name="premise_cache", status="ok", duration_ms=_elapsed_ms(stage_start), metadata={"cache_hit": True}, warnings=[])

        lock = self._single_flight_locks.setdefault(cache_key, asyncio.Lock())
        single_flight_waited = lock.locked()
        async with lock:
            cached = self._premise_cache.get(cache_key)
            if cached is not None:
                return cached, True, single_flight_waited, TraceStage(name="premise_cache", status="ok", duration_ms=_elapsed_ms(stage_start), metadata={"cache_hit": True}, warnings=[])
            try:
                converted = await self._convert_premises(cache_key, premises_nl)
            except _RequestTimeoutError as exc:
                return _PremiseBundle(frames=[], asts=[]), False, single_flight_waited, TraceStage(name="premise_timeout", status="failed", duration_ms=_elapsed_ms(stage_start), warnings=[str(exc)], metadata={"cache_hit": False})
            except Exception as exc:
                metadata: dict[str, Any] = {"cache_hit": False}
                if isinstance(exc, FrameExtractionError):
                    metadata.update(_safe_frame_error_metadata(exc))
                return _PremiseBundle(frames=[], asts=[]), False, single_flight_waited, TraceStage(name="premise_conversion", status="failed", duration_ms=_elapsed_ms(stage_start), warnings=[str(exc)], metadata=metadata)
            self._premise_cache[cache_key] = converted
            return converted, False, single_flight_waited, TraceStage(name="premise_conversion", status="ok", duration_ms=_elapsed_ms(stage_start), metadata={"cache_hit": False}, warnings=[])

    async def _convert_premises(self, cache_key: str, premises_nl: list[str]) -> _PremiseBundle:
        frames: list[ParseFrame] = []
        asts: list[LogicNode] = []
        for index, premise_text in enumerate(premises_nl, start=1):
            request = FrameExtractionInput(mode="premise", source_id=f"premise_{index:04d}", source_text=premise_text, premise_id=index)
            frame_result = await self._extract_frame_with_timeout(request)
            frames.append(frame_result.frame)
            asts.append(compile_frame_to_ast(frame_result.frame))
        self._premise_conversion_counts[cache_key] = self._premise_conversion_counts.get(cache_key, 0) + 1
        return _PremiseBundle(frames=frames, asts=asts)

    async def _compile_candidate_claims(self, candidate_result) -> tuple[list[LogicNode], TraceStage]:
        stage_start = time.perf_counter()
        asts: list[LogicNode] = []
        try:
            for candidate in candidate_result.candidates:
                request = FrameExtractionInput(
                    mode="candidate",
                    source_id=candidate.source_id,
                    source_text=candidate.text,
                    candidate_label=candidate.label,
                    metadata={"question_type": candidate.question_type},
                )
                frame_result = await self._extract_frame_with_timeout(request)
                asts.append(compile_frame_to_ast(frame_result.frame))
            return asts, TraceStage(name="candidate_compilation", status="ok", duration_ms=_elapsed_ms(stage_start), metadata={"candidate_ast_count": len(asts)}, warnings=[])
        except _RequestTimeoutError as exc:
            return [], TraceStage(name="candidate_timeout", status="failed", duration_ms=_elapsed_ms(stage_start), metadata={"candidate_ast_count": len(asts)}, warnings=[str(exc)])
        except (FrameExtractionError, ValueError) as exc:
            metadata: dict[str, Any] = {"candidate_ast_count": len(asts)}
            if isinstance(exc, FrameExtractionError):
                metadata.update(_safe_frame_error_metadata(exc))
            return [], TraceStage(name="candidate_compilation", status="failed", duration_ms=_elapsed_ms(stage_start), metadata=metadata, warnings=[str(exc)])

    async def _extract_frame_with_timeout(self, request: FrameExtractionInput):
        try:
            return await asyncio.wait_for(self._frame_extractor.extract_frame(request), timeout=self._request_timeout_seconds)
        except asyncio.TimeoutError as exc:
            raise _RequestTimeoutError(
                f"Frame extraction timed out after {self._request_timeout_seconds:.3f}s for {request.source_id}"
            ) from exc
        except FrameExtractionError as exc:
            diagnostics = dict(exc.diagnostics)
            diagnostics.setdefault("source_id", request.source_id)
            diagnostics.setdefault("frame_mode", request.mode)
            if request.premise_id is not None:
                diagnostics.setdefault("premise_id", request.premise_id)
            if request.candidate_label is not None:
                diagnostics.setdefault("candidate_label", request.candidate_label)
            raise FrameExtractionError(str(exc), diagnostics=diagnostics) from exc

    def _build_failure_result(
        self,
        context: _SampleContext,
        *,
        started_at: float,
        root_cause_category: str,
        root_cause_message: str,
        stage_name: str,
        cache_mode: Literal["local", "api"],
        cache_key: str | None,
        cache_hit: bool | None,
        single_flight_waited: bool | None,
        question_type: str | None,
        stages: list[TraceStage] | None = None,
    ) -> PipelineSampleResult:
        base_stages = list(stages or [])
        if not base_stages or base_stages[-1].status != "failed":
            base_stages.append(
                TraceStage(
                    name=stage_name,
                    status="failed",
                    duration_ms=0.0,
                    warnings=[root_cause_message],
                    metadata={},
                )
            )
        trace = DebugTrace(
            sample_id=context.sample_id,
            record_id=context.record_id,
            question_id=context.question_id,
            status="failed",
            root_cause_category=root_cause_category,
            root_cause_message=root_cause_message,
            created_at=_utc_now_iso(),
            total_duration_ms=_elapsed_ms(started_at),
            premises_hash=_cache_key_digest(cache_key) if cache_key else None,
            warnings=[],
            stages=base_stages,
            cache=CacheMetadata(
                mode=cache_mode,
                cache_key=cache_key,
                cache_key_hash=_cache_key_digest(cache_key) if cache_key else None,
                cache_hit=cache_hit,
                single_flight_waited=single_flight_waited,
            ),
            metadata={"question_type": question_type},
        )
        return PipelineSampleResult(
            sample_id=context.sample_id,
            record_id=context.record_id,
            question_id=context.question_id,
            answer="Unknown",
            explanation="Pipeline failed before a final answer could be produced.",
            status="failed",
            question_type=question_type,
            cache_mode=cache_mode,
            cache_key=cache_key,
            cache_hit=cache_hit,
            single_flight_waited=single_flight_waited,
            solver_handoff_ready=False,
            error=root_cause_message,
            trace=trace,
        )


def _elapsed_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000.0, 3)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _cache_key_digest(cache_key: str) -> str:
    return hashlib.sha256(cache_key.encode("utf-8")).hexdigest()


def _negate_claim(node: LogicNode) -> LogicNode:
    if isinstance(node, NotNode):
        return node.body
    return NotNode(
        type="not",
        body=node,
        source_id=getattr(node, "source_id", None),
        source_text=getattr(node, "source_text", None),
        premise_id=getattr(node, "premise_id", None),
        candidate_label=getattr(node, "candidate_label", None),
        confidence=getattr(node, "confidence", None),
    )


def _unique_strings(items: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _safe_frame_error_metadata(exc: FrameExtractionError) -> dict[str, Any]:
    diagnostics = dict(exc.diagnostics)
    safe_keys = (
        "source_id",
        "frame_mode",
        "premise_id",
        "candidate_label",
        "failure_type",
        "model",
        "prompt_version",
        "extractor_version",
        "endpoint",
        "attempts",
        "repair_count",
        "retry_count",
        "normalization_applied",
        "normalization_warnings",
    )
    metadata = {key: diagnostics[key] for key in safe_keys if key in diagnostics}
    if diagnostics.get("errors"):
        metadata["frame_errors"] = list(diagnostics["errors"])
    return metadata
