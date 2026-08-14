#!/usr/bin/env python3

import argparse
import csv
from pathlib import Path


DEFAULT_PROJECTS = [
    "Hadoop",
    "OpenStack",
    "BGL",
    "Thunderbird",
    "Linux",
    "Mac",
    "HealthApp",
    "OpenSSH",
]

OUTPUT_FIELDS = ["LineId", "Time", "Level", "Content", "EventId", "EventTemplate"]


def sample_project(src_csv: Path, dst_csv: Path, sample_size: int = 30) -> tuple[int, int]:
    rows = []
    seen_templates = set()

    with src_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        all_rows = list(reader)

    required = {"LineId", "Time", "Content", "EventId", "EventTemplate"}
    missing = required - set(all_rows[0].keys()) if all_rows else required
    if missing:
        raise ValueError(f"{src_csv.name} is missing required columns: {sorted(missing)}")

    for row in all_rows:
        template = row["EventTemplate"]
        if template in seen_templates:
            continue
        seen_templates.add(template)
        rows.append({field: row.get(field, "") for field in OUTPUT_FIELDS})
        if len(rows) == sample_size:
            break

    if len(rows) < sample_size:
        used_lineids = {row["LineId"] for row in rows}
        for row in all_rows:
            if row["LineId"] in used_lineids:
                continue
            rows.append({field: row.get(field, "") for field in OUTPUT_FIELDS})
            used_lineids.add(row["LineId"])
            if len(rows) == sample_size:
                break

    if len(rows) != sample_size:
        raise ValueError(f"{src_csv.name} produced {len(rows)} rows, expected {sample_size}")

    dst_csv.parent.mkdir(parents=True, exist_ok=True)
    with dst_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    unique_templates = len({row["EventTemplate"] for row in rows})
    return len(rows), unique_templates


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sample selected projects into per-project CSV files with a unified schema."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("RQ1/dataset/all_projects/2k_dataset"),
        help="Directory containing per-project source folders.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("RQ1/dataset/runtime_log"),
        help="Directory for sampled CSV outputs.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=30,
        help="Number of rows to export for each selected project.",
    )
    parser.add_argument(
        "--projects",
        nargs="+",
        default=DEFAULT_PROJECTS,
        help="Projects to sample. Defaults to the current RQ1 selection.",
    )
    args = parser.parse_args()

    for project in args.projects:
        project_dir = args.input_dir / project
        matches = list(project_dir.glob("*_structured_corrected.csv"))
        if len(matches) != 1:
            raise ValueError(
                f"{project}: expected exactly one *_structured_corrected.csv file, found {len(matches)}"
            )

        src_csv = matches[0]
        dst_csv = args.output_dir / f"{project}_selected_{args.sample_size}.csv"
        rows, unique_templates = sample_project(src_csv, dst_csv, args.sample_size)
        print(
            f"{project}\tsource={src_csv.name}\toutput={dst_csv.name}\trows={rows}\t"
            f"unique_templates={unique_templates}"
        )


if __name__ == "__main__":
    main()
