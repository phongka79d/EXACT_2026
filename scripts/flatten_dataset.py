import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("data/raw/Logic_Based_Educational_Queries.json")
DEFAULT_OUTPUT = Path("data/processed/Logic_Based_Educational_Queries.flattened.json")


def _get_optional(items: list[Any] | None, index: int) -> Any:
    if items is None or index >= len(items):
        return None
    return items[index]


def flatten_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []

    for record_id, record in enumerate(records):
        questions = record.get("questions") or []
        answers = record.get("answers")
        explanations = record.get("explanation")
        idx_values = record.get("idx")

        for question_id, question in enumerate(questions):
            flattened.append(
                {
                    "sample_id": f"record_{record_id:04d}_question_{question_id:04d}",
                    "record_id": record_id,
                    "question_id": question_id,
                    "premises-NL": record.get("premises-NL", []),
                    "premises-FOL": record.get("premises-FOL"),
                    "question": question,
                    "answer": _get_optional(answers, question_id),
                    "explanation": _get_optional(explanations, question_id),
                    "idx": _get_optional(idx_values, question_id),
                }
            )

    return flattened


def load_records(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON list in {path}")
    return data


def write_records(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(records, file, ensure_ascii=False, indent=2)
        file.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Flatten EXACT 2026 records into one sample per question.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    records = load_records(args.input)
    flattened = flatten_records(records)
    write_records(args.output, flattened)
    print(f"Wrote {len(flattened)} flattened samples to {args.output}")


if __name__ == "__main__":
    main()
