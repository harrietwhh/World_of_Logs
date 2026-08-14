#!/usr/bin/env python3
"""Build CSV data for fig:rq22-four-month-coverage-trends."""

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
    normalize_entities,
    parse_date_bound,
    parse_datetime,
    release_window,
    require_pymongo,
    selected_source_keys,
    validate_source_specs,
    write_csv,
)


COVERAGE_SOURCES = ["jira", "so"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build RQ2.2 JIRA/SO four-month coverage metrics."
    )
    add_common_args(parser)
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Top-k entity share for the coverage/concentration figure.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        require_pymongo()
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 2

    specs = build_source_specs(args)
    selected_sources = [
        source for source in selected_source_keys(args, specs) if source in COVERAGE_SOURCES
    ]
    if not selected_sources:
        raise ValueError("Coverage trends only support sources: jira, so")
    validate_source_specs(specs, selected_sources)
    start_date = parse_date_bound(args.start_date, "--start-date")
    end_date = parse_date_bound(args.end_date, "--end-date")
    if start_date >= end_date:
        raise ValueError("--start-date must be earlier than --end-date")

    source_metrics: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    window_bounds: dict[str, tuple[str, str]] = {}
    window_entities: dict[tuple[str, str], set[str]] = defaultdict(set)
    entity_doc_counts: Counter[tuple[str, str, str]] = Counter()
    entity_log_doc_counts: Counter[tuple[str, str, str]] = Counter()
    log_docs_by_entity: dict[tuple[str, str, str], set[str]] = defaultdict(set)
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
                include_entities=True,
            ):
                collection_counts[(source_key, collection_name)] += 1
                created_at = parse_datetime(doc.get("created_at"))
                if created_at is None:
                    skipped_invalid_created_at[source_key] += 1
                    continue

                doc_id = str(first_value(doc, DOC_ID_FIELDS) or "")
                if not doc_id:
                    doc_id = f"{spec.db}.{collection_name}:{collection_counts[(source_key, collection_name)]}"

                window, window_start, window_end = release_window(
                    created_at,
                    args.window_months,
                    args.window_anchor_month,
                )
                window_bounds[window] = (window_start, window_end)

                try:
                    has_log, _ = infer_log_metrics(doc)
                except MissingLogCountError:
                    skipped_missing_log_count[source_key] += 1
                    examples = skipped_missing_log_count_examples[source_key]
                    if len(examples) < 10:
                        examples.append(
                            doc_id
                            or f"{collection_name}:{collection_counts[(source_key, collection_name)]}"
                        )
                    continue
                entities = normalize_entities(source_key, first_value(doc, spec.entity_fields))

                metric_key = (source_key, window)
                source_metrics[metric_key]["inferred_log_docs"] += int(has_log)
                window_entities[metric_key].update(entities)
                for entity in entities:
                    entity_key = (source_key, window, entity)
                    entity_doc_counts[entity_key] += 1
                    entity_log_doc_counts[entity_key] += int(has_log)
                if has_log:
                    for entity in entities:
                        log_docs_by_entity[(source_key, window, entity)].add(doc_id)

    rows: list[dict[str, Any]] = []
    for source_key in COVERAGE_SOURCES:
        if source_key not in selected_sources:
            continue
        spec = specs[source_key]
        cumulative_entities: set[str] = set()
        windows = sorted(window for key, window in source_metrics if key == source_key)
        for window in windows:
            metric_key = (source_key, window)
            per_entity_counts = {
                entity: len(doc_ids)
                for (key, entity_window, entity), doc_ids in log_docs_by_entity.items()
                if key == source_key and entity_window == window
            }
            log_entities = {entity for entity, count in per_entity_counts.items() if count > 0}
            cumulative_entities.update(log_entities)

            top_entities = [
                entity
                for entity, _ in Counter(per_entity_counts).most_common(args.top_k)
            ]
            covered_doc_ids = set()
            for entity in top_entities:
                covered_doc_ids.update(log_docs_by_entity[(source_key, window, entity)])

            inferred_log_docs = source_metrics[metric_key]["inferred_log_docs"]
            rows.append(
                {
                    "source": spec.label,
                    "source_key": source_key,
                    "entity_type": spec.entity_type,
                    "release_window": window,
                    "window_start": window_bounds[window][0],
                    "window_end": window_bounds[window][1],
                    "window_entities": len(window_entities[metric_key]),
                    "entities_with_logs": len(log_entities),
                    "cumulative_log_entities": len(cumulative_entities),
                    f"top{args.top_k}_share": fmt_float(
                        len(covered_doc_ids) / inferred_log_docs
                        if inferred_log_docs
                        else None
                    ),
                    "inferred_log_docs": inferred_log_docs,
                }
            )

    entity_rows: list[dict[str, Any]] = []
    for source_key, window, entity in sorted(entity_doc_counts):
        if source_key not in selected_sources:
            continue
        spec = specs[source_key]
        num_docs = entity_doc_counts[(source_key, window, entity)]
        inferred_log_docs = entity_log_doc_counts[(source_key, window, entity)]
        entity_rows.append(
            {
                "source": spec.label,
                "source_key": source_key,
                "entity_type": spec.entity_type,
                "release_window": window,
                "window_start": window_bounds[window][0],
                "window_end": window_bounds[window][1],
                "entity_id": entity,
                "num_docs": num_docs,
                "inferred_log_docs": inferred_log_docs,
                "log_doc_rate": fmt_float(
                    inferred_log_docs / num_docs if num_docs else None
                ),
            }
        )

    run_output_dir = make_run_output_dir(
        args.output_dir, "coverage_trends", selected_sources
    )
    output_path = run_output_dir / "rq22_four_month_coverage_trends.csv"
    entity_counts_path = run_output_dir / "rq22_coverage_entity_window_counts.csv"
    write_csv(
        output_path,
        rows,
        [
            "source",
            "source_key",
            "entity_type",
            "release_window",
            "window_start",
            "window_end",
            "window_entities",
            "entities_with_logs",
            "cumulative_log_entities",
            f"top{args.top_k}_share",
            "inferred_log_docs",
        ],
    )
    write_csv(
        entity_counts_path,
        entity_rows,
        [
            "source",
            "source_key",
            "entity_type",
            "release_window",
            "window_start",
            "window_end",
            "entity_id",
            "num_docs",
            "inferred_log_docs",
            "log_doc_rate",
        ],
    )

    metadata_path = run_output_dir / "rq22_four_month_coverage_trends_metadata.json"
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
        "top_k": args.top_k,
        "output_csv": str(output_path),
        "entity_counts_csv": str(entity_counts_path),
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
    print(f"Wrote coverage trend data to {output_path}")
    print(f"Wrote entity window counts to {entity_counts_path}")
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
