"""Credential-gated live parse-frame smoke check for Batch 8.6."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.config import EnvConfigError
from app.llm import FrameExtractionError, FrameExtractionInput, build_default_llm_frame_extractor


async def run_smoke(env_path: str | Path, timeout_seconds: float, max_attempts: int) -> tuple[dict[str, Any], int]:
    try:
        extractor = build_default_llm_frame_extractor(
            str(env_path),
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
            max_repairs=5,
        )
    except EnvConfigError as exc:
        return (
            {
                "status": "blocked",
                "reason": "missing_or_invalid_env",
                "detail": str(exc),
            },
            2,
        )

    request = FrameExtractionInput(
        mode="premise",
        source_id="premise_0001",
        premise_id=1,
        source_text="Student Alex has a cumulative GPA of 7.2.",
    )

    try:
        result = await extractor.extract_frame(request)
    except FrameExtractionError as exc:
        diagnostics = dict(exc.diagnostics)
        failure_type = diagnostics.get("failure_type")
        status = "blocked" if failure_type == "provider_error" else "failed"
        reason = "network_or_provider_unavailable" if status == "blocked" else "invalid_parse_frame_output"
        return (
            {
                "status": status,
                "reason": reason,
                "detail": str(exc),
                "diagnostics": diagnostics,
            },
            2 if status == "blocked" else 1,
        )

    return (
        {
            "status": "passed",
            "model": result.diagnostics.get("model"),
            "endpoint": result.diagnostics.get("endpoint"),
            "frame_kind": getattr(result.frame, "kind", "unknown"),
            "cache_hit": result.diagnostics.get("cache_hit"),
            "attempts": result.diagnostics.get("attempts"),
            "repair_count": result.diagnostics.get("repair_count"),
        },
        0,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run live compact parse-frame smoke validation.")
    parser.add_argument("--env-path", default=".env", help="Path to .env file")
    parser.add_argument("--timeout-seconds", type=float, default=20.0, help="HTTP timeout in seconds")
    parser.add_argument("--max-attempts", type=int, default=3, help="Transient retry attempts per request")
    args = parser.parse_args()

    result, exit_code = asyncio.run(
        run_smoke(
            env_path=args.env_path,
            timeout_seconds=args.timeout_seconds,
            max_attempts=args.max_attempts,
        )
    )
    print(json.dumps(result, ensure_ascii=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
