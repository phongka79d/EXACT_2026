"""Local async evaluation runner for the runtime pipeline."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.config import load_runtime_config
from app.data import load_runtime_samples
from app.llm import EXTRACTOR_VERSION, PROMPT_VERSION, build_default_llm_frame_extractor
from app.pipeline import AsyncRuntimePipeline, write_pipeline_artifacts


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local async orchestration and write prediction/debug artifacts.")
    parser.add_argument("--input", default="data/processed/Logic_Based_Educational_Queries.flattened.json", help="Flattened local input dataset.")
    parser.add_argument("--output-dir", default="artifacts/local_eval", help="Directory for predictions/debug artifacts.")
    parser.add_argument("--env-path", default=".env", help="Path to .env file.")
    parser.add_argument("--max-concurrency", type=int, default=8, help="Maximum concurrent sample workers.")
    parser.add_argument("--request-timeout-seconds", type=float, default=20.0, help="Per-frame-extraction timeout.")
    parser.add_argument("--sample-timeout-seconds", type=float, default=60.0, help="Per-sample timeout.")
    parser.add_argument("--max-attempts", type=int, default=3, help="Transient retry attempts per LLM request.")
    args = parser.parse_args()

    runtime_config = load_runtime_config(args.env_path)
    extractor = build_default_llm_frame_extractor(
        env_path=args.env_path,
        timeout_seconds=args.request_timeout_seconds,
        max_attempts=args.max_attempts,
        max_repairs=1,
    )
    pipeline = AsyncRuntimePipeline(
        frame_extractor=extractor,
        max_concurrency=args.max_concurrency,
        request_timeout_seconds=args.request_timeout_seconds,
        sample_timeout_seconds=args.sample_timeout_seconds,
        api_hash_components=(
            f"model={runtime_config.shopaikey_model}",
            f"prompt={PROMPT_VERSION}",
            f"extractor={EXTRACTOR_VERSION}",
            "compiler=frame_compiler_v1",
        ),
    )

    samples = load_runtime_samples(args.input)
    results = asyncio.run(pipeline.process_local_samples(samples))
    artifacts = write_pipeline_artifacts(args.output_dir, results)

    summary = {
        "status": "ok",
        "total_samples": len(results),
        "ok_samples": sum(1 for item in results if item.status == "ok"),
        "partial_samples": sum(1 for item in results if item.status == "partial"),
        "failed_samples": sum(1 for item in results if item.status == "failed"),
        "predictions_path": artifacts.predictions_path,
        "debug_traces_path": artifacts.debug_traces_path,
    }
    print(json.dumps(summary, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
