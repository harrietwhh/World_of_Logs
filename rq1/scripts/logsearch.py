#!/usr/bin/env python3

import argparse
import csv
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT_DIR = Path("RQ1/search_results/logsearch")
DEFAULT_BASE_URL = "http://129.97.92.71:8000/api/search"
MANIFEST_FIELDS = [
    "batch_index",
    "line_id",
    "event_id",
    "event_template",
    "query_text",
    "normalized_results_file",
    "requested_at_utc",
    "num_results",
    "status",
    "error_message",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Query the log search API for each row in a selected-project CSV."
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        required=True,
        help="Path to the input CSV whose query column will be searched row by row.",
    )
    parser.add_argument(
        "--query-column",
        default="Content",
        help="Column whose content is used as the search query. Defaults to `Content`.",
    )
    parser.add_argument(
        "--num",
        type=int,
        default=10,
        help="Maximum number of results to save per query.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=5.0,
        help="Seconds to sleep between consecutive requests.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Base directory where batch search results will be saved.",
    )
    parser.add_argument(
        "--run-label",
        default=None,
        help="Optional suffix for the batch directory name.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="Search API endpoint URL.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout in seconds.",
    )
    return parser.parse_args()


def build_batch_dir(base_dir: Path, input_csv: Path, run_label: str | None) -> Path:
    batch_name = input_csv.stem if not run_label else f"{input_csv.stem}__{run_label}"
    return base_dir / batch_name


def fetch_search_results(
    query: str,
    base_url: str,
    timeout: float,
) -> tuple[dict[str, Any], str]:
    request_url = f"{base_url}?{urllib.parse.urlencode({'query': query})}"
    request = urllib.request.Request(
        request_url,
        headers={
            "Accept": "application/json",
            "User-Agent": "logsearch.py/1.0",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        reason = exc.reason if hasattr(exc, "reason") else exc
        raise RuntimeError(f"Search request failed for {request_url}: {reason}") from exc

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Search API did not return valid JSON. "
            f"Endpoint: {request_url}. Response prefix: {payload[:200]!r}"
        ) from exc

    if not isinstance(data, dict):
        raise RuntimeError(
            "Unexpected response type from search API. "
            f"Expected JSON object but got {type(data).__name__}."
        )

    return data, request_url


def normalize_items(items: list[dict[str, Any]], num: int) -> list[dict[str, Any]]:
    normalized = []
    for rank, item in enumerate(items[:num], start=1):
        metadata = item.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        normalized.append(
            {
                "rank": rank,
                "id": item.get("id", ""),
                "score": item.get("score", ""),
                "link": item.get("url", ""),
                "source": metadata.get("source", ""),
                "origin_doc_id": metadata.get("origin_doc_id", ""),
                "snippet": item.get("text", ""),
            }
        )
    return normalized


def write_json(path: Path, payload: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def write_manifest(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def load_input_rows(input_csv: Path, query_column: str) -> list[dict[str, str]]:
    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")

    with input_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        required_columns = {"LineId", query_column}
        missing = required_columns - set(fieldnames)
        if missing:
            raise ValueError(
                f"{input_csv.name} is missing required columns: {sorted(missing)}"
            )
        rows = list(reader)

    if not rows:
        raise ValueError(f"{input_csv.name} does not contain any data rows.")

    seen_line_ids = set()
    duplicates = set()
    for row in rows:
        line_id = (row.get("LineId") or "").strip()
        if not line_id:
            raise ValueError(f"{input_csv.name} contains an empty LineId value.")
        if line_id in seen_line_ids:
            duplicates.add(line_id)
        seen_line_ids.add(line_id)

    if duplicates:
        duplicate_values = ", ".join(sorted(duplicates))
        raise ValueError(
            f"{input_csv.name} contains duplicate LineId values: {duplicate_values}"
        )

    return rows


def main() -> None:
    args = parse_args()
    if args.num < 1:
        raise ValueError("--num must be at least 1.")
    if args.sleep_seconds < 0:
        raise ValueError("--sleep-seconds must be non-negative.")
    if args.timeout <= 0:
        raise ValueError("--timeout must be positive.")

    rows = load_input_rows(args.input_csv, args.query_column)

    batch_dir = build_batch_dir(args.output_dir, args.input_csv, args.run_label)
    normalized_dir = batch_dir / "normalized_results"
    normalized_dir.mkdir(parents=True, exist_ok=True)

    total_query_candidates = sum(
        1 for row in rows if (row.get(args.query_column) or "").strip()
    )

    started_at = datetime.now(timezone.utc).isoformat()
    manifest_rows: list[dict[str, Any]] = []
    attempted_queries = 0
    success_count = 0
    zero_result_count = 0
    failure_count = 0
    skipped_count = 0

    for batch_index, row in enumerate(rows, start=1):
        line_id = (row.get("LineId") or "").strip()
        query_text = (row.get(args.query_column) or "").strip()
        event_id = row.get("EventId", "")
        event_template = row.get("EventTemplate", "")

        manifest_row: dict[str, Any] = {
            "batch_index": batch_index,
            "line_id": line_id,
            "event_id": event_id,
            "event_template": event_template,
            "query_text": query_text,
            "normalized_results_file": "",
            "requested_at_utc": "",
            "num_results": "",
            "status": "",
            "error_message": "",
        }

        if not query_text:
            skipped_count += 1
            manifest_row["status"] = "skipped_empty_query"
            manifest_row["error_message"] = f"Column `{args.query_column}` is empty."
            manifest_rows.append(manifest_row)
            print(f"[{batch_index}/{len(rows)}] LineId={line_id} skipped (empty query)")
            continue

        attempted_queries += 1
        requested_at = datetime.now(timezone.utc).isoformat()
        manifest_row["requested_at_utc"] = requested_at

        query_preview = query_text[:80] + ("..." if len(query_text) > 80 else "")
        print(f"[{batch_index}/{len(rows)}] LineId={line_id} querying: {query_preview}")

        try:
            raw_response, request_url = fetch_search_results(
                query=query_text,
                base_url=args.base_url,
                timeout=args.timeout,
            )
            items = raw_response.get("results", [])
            if not isinstance(items, list):
                raise RuntimeError(
                    "Unexpected response shape from search API: `results` is not a list."
                )

            normalized = normalize_items(items, args.num)
            result_filename = f"{line_id}.json"
            write_json(normalized_dir / result_filename, normalized)

            manifest_row["normalized_results_file"] = f"normalized_results/{result_filename}"
            manifest_row["num_results"] = len(normalized)
            manifest_row["status"] = "success"
            manifest_row["error_message"] = ""
            success_count += 1
            if not normalized:
                zero_result_count += 1
                print(
                    f"[{batch_index}/{len(rows)}] LineId={line_id} success, "
                    "results=0 (saved empty JSON array)"
                )
            else:
                print(
                    f"[{batch_index}/{len(rows)}] LineId={line_id} success, "
                    f"results={len(normalized)}"
                )
        except Exception as exc:
            manifest_row["status"] = "error"
            manifest_row["error_message"] = str(exc)
            failure_count += 1
            print(f"[{batch_index}/{len(rows)}] LineId={line_id} failed: {exc}")

        manifest_rows.append(manifest_row)

        if attempted_queries < total_query_candidates and args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)

    finished_at = datetime.now(timezone.utc).isoformat()
    batch_metadata = {
        "input_csv": str(args.input_csv),
        "query_column": args.query_column,
        "requested_num": args.num,
        "sleep_seconds": args.sleep_seconds,
        "provider": "LogSearch API",
        "engine": "logsearch",
        "endpoint": args.base_url,
        "timeout_seconds": args.timeout,
        "batch_name": batch_dir.name,
        "output_files": {
            "batch_metadata": "batch_metadata.json",
            "query_manifest": "query_manifest.csv",
            "normalized_results_dir": "normalized_results/",
        },
        "total_rows_seen": len(rows),
        "total_query_candidates": total_query_candidates,
        "total_queries_attempted": attempted_queries,
        "total_successes": success_count,
        "total_zero_result_successes": zero_result_count,
        "total_failures": failure_count,
        "total_skipped_empty_query": skipped_count,
        "started_at_utc": started_at,
        "finished_at_utc": finished_at,
    }

    write_manifest(batch_dir / "query_manifest.csv", manifest_rows)
    write_json(batch_dir / "batch_metadata.json", batch_metadata)

    print(f"Batch results saved to: {batch_dir}")
    print(
        "Summary: "
        f"rows={len(rows)}, attempted={attempted_queries}, "
        f"successes={success_count}, zero_result_successes={zero_result_count}, "
        f"failures={failure_count}, skipped={skipped_count}"
    )


if __name__ == "__main__":
    main()


# usage
# python3 RQ1/scripts/logsearch.py \
#   --input-csv RQ1/dataset/runtime_log/OpenSSH_selected_30.csv

# python3 -u RQ1/scripts/logsearch.py \
#   --input-csv RQ1/dataset/runtime_log/OpenSSH_selected_30.csv \
#   > RQ1/search_results/logsearch/OpenSSH_selected_30/logsearch.log 2>&1

# python3 -u RQ1/scripts/logsearch.py \
#   --input-csv RQ1/dataset/build_log/Travis_CI_chunks.csv \
#   > RQ1/search_results/logsearch/Travis_CI_chunks/logsearch.log 2>&1


# mkdir -p RQ1/search_results/logsearch/AL_Bench_doris_log
# python3 -u RQ1/scripts/logsearch.py \
#   --input-csv RQ1/dataset/logging_stmt/AL_Bench_doris_log.csv \
#   --query-column LogStatement \
#   > RQ1/search_results/logsearch/AL_Bench_doris_log/logsearch.log 2>&1

# mkdir -p RQ1/search_results/logsearch/Apache_testing_log
# python3 -u RQ1/scripts/logsearch.py \
#   --input-csv RQ1/dataset/testing_log/testing_log_semantic_diverse_30.csv \
#   > RQ1/search_results/logsearch/Apache_testing_log/logsearch.log 2>&1