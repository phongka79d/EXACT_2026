"""Credential-gated live parse-frame smoke check for Batch 5."""

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


def _success_payload_from_result(result: Any) -> dict[str, Any]:
    diagnostics = dict(result.diagnostics)
    payload: dict[str, Any] = {
        "status": "passed",
        "model": diagnostics.get("model"),
        "endpoint": diagnostics.get("endpoint"),
        "frame_kind": getattr(result.frame, "kind", "unknown"),
        "cache_hit": diagnostics.get("cache_hit"),
        "attempts": diagnostics.get("attempts"),
        "retry_count": diagnostics.get("retry_count"),
        "repair_count": diagnostics.get("repair_count"),
        "normalization_applied": diagnostics.get("normalization_applied"),
        "normalization_warnings": diagnostics.get("normalization_warnings", []),
    }
    if (diagnostics.get("repair_count") or 0) > 0:
        payload["repair_errors"] = list(diagnostics.get("errors") or [])
    return payload


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

    return (_success_payload_from_result(result), 0)


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
