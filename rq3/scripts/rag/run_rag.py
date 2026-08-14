#!/usr/bin/env python3
"""Run the explanation RAG condition once per case."""

import argparse
import csv
import json
from pathlib import Path

try:
    from ..api_router import get_chat_completion
    from ..prompt_templates import build_explanation_prompt
except ImportError:  # Running directly: python scripts/rag/run_rag.py
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from api_router import get_chat_completion
    from prompt_templates import build_explanation_prompt


def build_prompt(group_logs: str, external_info: str) -> str:
    """Build the common prompt with RAG external information supplied."""
    return build_explanation_prompt(group_logs, external_info)


def build_messages(group_logs: str, external_info: str) -> list[dict[str, str]]:
    return [{"role": "system", "content": build_prompt(group_logs, external_info)}]


def _case_key(row: dict[str, str]) -> str:
    return f"{row.get('project', '').strip()}:{row.get('case_id', '').strip()}"


def _write_results(path: Path, results: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def run_rag(input_csv: Path, output_json: Path, limit: int | None = None) -> int:
    """Query the model once per row and save each result immediately."""
    with input_csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    if limit is not None:
        rows = rows[:limit]

    results: list[dict] = []
    for index, row in enumerate(rows, start=1):
        project = row.get("project", "").strip()
        case_id = row.get("case_id", "").strip()
        group_logs = row.get("group_logs", "")
        external_info = row.get("external_knowledge_summary", "")
        if not project or not case_id:
            raise ValueError(f"Missing project/case_id at CSV row {index + 1}")

        record = {
            "case_key": _case_key(row),
            "project": project,
            "case_id": case_id,
            "group_logs": group_logs,
            "external_knowledge_summary": external_info,
        }
        try:
            # Exactly one model request is made for each input row.
            record["explanation"] = get_chat_completion(
                build_messages(group_logs, external_info)
            )
            record["error"] = None
        except Exception as exc:  # Keep completed cases when one API call fails.
            record["explanation"] = None
            record["error"] = f"{type(exc).__name__}: {exc}"
        results.append(record)
        _write_results(output_json, results)
        print(f"[{index}/{len(rows)}] {record['case_key']}")

    return len(results)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=Path("data/sample/experiment_samples_rag.csv"),
        help="CSV containing project, case_id, group_logs, and external_knowledge_summary.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("results/rag/rag_explanations.json"),
        help="Output JSON path.",
    )
    parser.add_argument("--limit", type=int, help="Only process the first N cases.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    count = run_rag(args.input_csv, args.output_json, args.limit)
    print(f"Wrote {count} case results to {args.output_json}")


if __name__ == "__main__":
    main()
