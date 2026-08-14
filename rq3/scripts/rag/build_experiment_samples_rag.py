#!/usr/bin/env python3
"""Build the CSV input for the RAG explanation stage.

Run this script from the ``exp_w_api`` directory.  It joins the original
sample CSV with ``external_knowledge_summary`` from every summarizer JSON.
"""

import argparse
import csv
import json
from pathlib import Path


OUTPUT_FIELDS = [
    "project",
    "case_id",
    "group_logs",
    "external_knowledge_summary",
]


def _case_key(project: str, case_id: str) -> tuple[str, str]:
    return project.strip().lower(), str(case_id).strip()


def _load_summaries(summarizer_dir: Path) -> dict[tuple[str, str], str]:
    summaries: dict[tuple[str, str], str] = {}

    for json_path in sorted(summarizer_dir.rglob("*.json")):
        with json_path.open(encoding="utf-8") as handle:
            payload = json.load(handle)

        case_id = str(payload.get("case_id", "")).strip()
        if not case_id:
            raise ValueError(f"Missing case_id in {json_path}")

        project = str(payload.get("project", "")).strip()
        if not project:
            # Expected layout: summarizer_results/<project>/case_<id>/...json
            project = json_path.parent.parent.name

        summary = payload.get("external_knowledge_summary", "")
        if summary is None:
            summary = ""
        if not isinstance(summary, str):
            summary = str(summary)

        key = _case_key(project, case_id)
        if key in summaries:
            raise ValueError(f"Duplicate summarizer result for {project}:{case_id}")
        summaries[key] = summary

    return summaries


def build_csv(input_csv: Path, summarizer_dir: Path, output_csv: Path) -> int:
    summaries = _load_summaries(summarizer_dir)
    rows = []
    missing = []

    with input_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required_fields = {"project", "case_id", "group_logs"}
        missing_fields = required_fields - set(reader.fieldnames or [])
        if missing_fields:
            raise ValueError(f"Missing CSV fields: {sorted(missing_fields)}")

        for row in reader:
            project = row.get("project", "").strip()
            case_id = row.get("case_id", "").strip()
            key = _case_key(project, case_id)
            if key not in summaries:
                missing.append(f"{project}:{case_id}")
                continue

            rows.append(
                {
                    "project": project,
                    "case_id": case_id,
                    "group_logs": row.get("group_logs", ""),
                    "external_knowledge_summary": summaries[key],
                }
            )

    if missing:
        preview = ", ".join(missing[:10])
        suffix = " ..." if len(missing) > 10 else ""
        raise ValueError(f"No summarizer result for {len(missing)} sample case(s): {preview}{suffix}")

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=Path("data/sample/experiment_samples.csv"),
        help="Original sample CSV.",
    )
    parser.add_argument(
        "--summarizer-dir",
        type=Path,
        default=Path("summarizer_results"),
        help="Directory containing summarizer JSON files.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("data/sample/experiment_samples_rag.csv"),
        help="Output RAG CSV.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    count = build_csv(args.input_csv, args.summarizer_dir, args.output_csv)
    print(f"Wrote {count} rows to {args.output_csv}")


if __name__ == "__main__":
    main()
