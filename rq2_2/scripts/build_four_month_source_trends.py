#!/usr/bin/env python3
"""Build CSV data for fig:rq22-four-month-source-trends."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from rq22_common import (
    DOC_ID_FIELDS,
    MissingLogCountError,
    MongoClient,
    add_common_args,
    build_source_specs,
    first_value,
    fmt_float,
    infer_log_metrics,
    iter_source_docs,
    make_run_output_dir,
    parse_date_bound,
    parse_datetime,
    release_window,
    require_pymongo,
    selected_source_keys,
    validate_source_specs,
    write_csv,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build RQ2.2 source x four-month release-window metrics."
    )
    add_common_args(parser)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        require_pymongo()
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 2

    specs = build_source_specs(args)
    selected_sources = selected_source_keys(args, specs)
    validate_source_specs(specs, selected_sources)
    start_date = parse_date_bound(args.start_date, "--start-date")
    end_date = parse_date_bound(args.end_date, "--end-date")
    if start_date >= end_date:
        raise ValueError("--start-date must be earlier than --end-date")

    source_metrics: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    window_bounds: dict[str, tuple[str, str]] = {}
    collection_counts: Counter[tuple[str, str]] = Counter()
    skipped_invalid_created_at: Counter[str] = Counter()
    skipped_missing_log_count: Counter[str] = Counter()
    skipped_missing_log_count_examples: dict[str, list[str]] = defaultdict(list)

    with MongoClient(args.uri) as client:
        for source_key in selected_sources:
            spec = specs[source_key]
            for collection_name, doc in iter_source_docs(
                client,
                spec,
                args.limit_per_collection,
                start_date,
                end_date,
                include_entities=False,
            ):
                collection_counts[(source_key, collection_name)] += 1
                created_at = parse_datetime(doc.get("created_at"))
                if created_at is None:
                    skipped_invalid_created_at[source_key] += 1
                    continue

                window, window_start, window_end = release_window(
                    created_at,
                    args.window_months,
                    args.window_anchor_month,
                )
                window_bounds[window] = (window_start, window_end)
                try:
                    has_log, num_logs = infer_log_metrics(doc)
                except MissingLogCountError:
                    skipped_missing_log_count[source_key] += 1
                    examples = skipped_missing_log_count_examples[source_key]
                    if len(examples) < 10:
                        doc_id = str(first_value(doc, DOC_ID_FIELDS) or "")
                        examples.append(doc_id or f"{collection_name}:{collection_counts[(source_key, collection_name)]}")
                    continue

                metric_key = (source_key, window)
                source_metrics[metric_key]["num_new_docs"] += 1
                source_metrics[metric_key]["inferred_log_docs"] += int(has_log)
                source_metrics[metric_key]["num_logs"] += num_logs

    rows: list[dict[str, Any]] = []
    for source_key in selected_sources:
        spec = specs[source_key]
        windows = sorted(window for key, window in source_metrics if key == source_key)
        for window in windows:
            counts = source_metrics[(source_key, window)]
            num_new_docs = counts["num_new_docs"]
            inferred_log_docs = counts["inferred_log_docs"]
            num_logs = counts["num_logs"]
            rows.append(
                {
                    "source": spec.label,
                    "source_key": source_key,
                    "release_window": window,
                    "window_start": window_bounds[window][0],
                    "window_end": window_bounds[window][1],
                    "num_new_docs": num_new_docs,
                    "inferred_log_docs": inferred_log_docs,
                    "log_doc_rate": fmt_float(inferred_log_docs / num_new_docs),
                    "num_logs": num_logs,
                    "logs_per_log_doc": fmt_float(
                        num_logs / inferred_log_docs if inferred_log_docs else None
                    ),
                }
            )

    run_output_dir = make_run_output_dir(
        args.output_dir, "source_trends", selected_sources
    )
    output_path = run_output_dir / "rq22_four_month_source_trends.csv"
    write_csv(
        output_path,
        rows,
        [
            "source",
            "source_key",
            "release_window",
            "window_start",
            "window_end",
            "num_new_docs",
            "inferred_log_docs",
            "log_doc_rate",
            "num_logs",
            "logs_per_log_doc",
        ],
    )

    metadata_path = run_output_dir / "rq22_four_month_source_trends_metadata.json"
    metadata = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "uri": args.uri,
        "sources": selected_sources,
        "run_output_dir": str(run_output_dir),
        "window_months": args.window_months,
        "window_anchor_month": args.window_anchor_month,
        "time_field": "created_at",
        "start_date": start_date.isoformat(),
        "end_date_exclusive": end_date.isoformat(),
        "output_csv": str(output_path),
        "collections_read": {
            f"{source}/{collection}": count
            for (source, collection), count in sorted(collection_counts.items())
        },
        "skipped_missing_or_invalid_created_at": dict(skipped_invalid_created_at),
        "skipped_missing_or_invalid_log_count": dict(skipped_missing_log_count),
        "skipped_missing_or_invalid_log_count_examples": dict(
            skipped_missing_log_count_examples
        ),
    }
    with metadata_path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"Wrote run outputs to {run_output_dir}")
    print(f"Wrote source trend data to {output_path}")
    print(f"Wrote metadata to {metadata_path}")
    if skipped_missing_log_count:
        print(
            "Skipped documents with missing/invalid log count fields: "
            f"{dict(skipped_missing_log_count)}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
