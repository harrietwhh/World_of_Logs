#!/usr/bin/env python3
"""Utilities for combining case-study CSV data with generated explanations."""

import argparse
import csv
import json
from pathlib import Path


def _read_json_object(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return payload


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def merge_group_logs_with_explanations(
    csv_path: str | Path,
    explanation_path: str | Path,
    output_path: str | Path,
) -> dict:
    """Merge every CSV case with its explanation, using ``{}`` when absent.

    This generalizes the behavior of the original BGL post-processing script.
    The returned and saved mapping is keyed by ``case_id``.
    """

    csv_path = Path(csv_path)
    explanation_path = Path(explanation_path)
    output_path = Path(output_path)
    explanations = _read_json_object(explanation_path)
    merged = {}

    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            case_id = row["case_id"]
            merged[case_id] = {
                "case_id": case_id,
                "group_logs": row["group_logs"],
                "explanation": explanations.get(case_id, {}),
            }

    _write_json(output_path, merged)
    return merged


def merge_selected_explanations(
    csv_path: str | Path,
    explanation_path: str | Path,
    output_path: str | Path,
) -> dict:
    """Merge one selected-case explanation file with CSV logs and summaries.

    Only cases present in the explanation file are emitted, sorted by numeric
    ``case_id``.
    """

    csv_path = Path(csv_path)
    explanation_path = Path(explanation_path)
    output_path = Path(output_path)
    explanations = _read_json_object(explanation_path)

    selected = {}
    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            case_id = row["case_id"]
            if case_id not in explanations:
                continue
            selected[case_id] = {
                "case_id": case_id,
                "group_logs": row["group_logs"],
                "summary": row["summary"],
                "explanation": explanations[case_id],
            }

    merged = dict(sorted(selected.items(), key=lambda item: int(item[0])))
    _write_json(output_path, merged)
    return merged


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge case-study CSV rows with previously generated explanations."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    merge_all = subparsers.add_parser(
        "merge-all",
        help="Merge every CSV case with explanations from one JSON object.",
    )
    merge_all.add_argument("--csv", required=True, help="Input case-study CSV path.")
    merge_all.add_argument(
        "--explanations",
        required=True,
        help="Input explanation JSON path.",
    )
    merge_all.add_argument("--output", required=True, help="Output JSON path.")

    merge_selected = subparsers.add_parser(
        "merge-selected",
        help="Merge cases present in one explanation JSON object.",
    )
    merge_selected.add_argument("--csv", required=True, help="Input case-study CSV path.")
    merge_selected.add_argument(
        "--explanations",
        required=True,
        help="Input explanation JSON path.",
    )
    merge_selected.add_argument("--output", required=True, help="Output JSON path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "merge-all":
        merged = merge_group_logs_with_explanations(
            args.csv,
            args.explanations,
            args.output,
        )
    else:
        merged = merge_selected_explanations(
            args.csv,
            args.explanations,
            args.output,
        )
    print(f"Wrote {len(merged)} cases to {args.output}")


if __name__ == "__main__":
    main()
