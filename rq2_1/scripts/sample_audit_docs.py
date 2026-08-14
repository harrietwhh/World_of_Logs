#!/usr/bin/env python3
"""Sample RQ2.1 MongoDB documents for manual audit annotation."""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import source_common_crawl
import source_github
import source_jira
import source_so
from utils import (
    CollectionSpec,
    sample_documents,
    write_csv,
    write_metadata,
)

try:
    from pymongo import MongoClient
except ImportError:  # pragma: no cover - handled at runtime for user clarity
    MongoClient = None


SourceFactory = Callable[[dict[str, Any] | None], list[CollectionSpec]]

SOURCE_FACTORIES: dict[str, SourceFactory] = {
    "jira": source_jira.make_specs,
    "so": source_so.make_specs,
    "stack_overflow": source_so.make_specs,
    "github": source_github.make_specs,
    "cc": source_common_crawl.make_specs,
    "common_crawl": source_common_crawl.make_specs,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sample RQ2.1 positive/negative documents from MongoDB."
    )
    parser.add_argument("--mongo-uri", default=None, help="MongoDB URI.")
    parser.add_argument("--mongo-host", default="localhost", help="MongoDB host.")
    parser.add_argument("--mongo-port", type=int, default=27017, help="MongoDB port.")
    parser.add_argument("--seed", type=int, default=20260505, help="Random seed.")
    parser.add_argument("--positive-per-source", type=int, default=100)
    parser.add_argument("--negative-per-source", type=int, default=100)
    parser.add_argument(
        "--sources",
        nargs="+",
        default=["jira", "so"],
        help="Sources to sample: jira, github, so/stack_overflow, cc/common_crawl.",
    )
    parser.add_argument(
        "--source-config-json",
        type=Path,
        default=None,
        help=(
            "Optional JSON config keyed by source name. Each source may override "
            "db, collections, and created_since."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("RQ2/rq2.1/dataset/audit_samples"),
        help="Directory where one source-specific CSV will be written per source.",
    )
    parser.add_argument(
        "--metadata-output",
        type=Path,
        default=Path("RQ2/rq2.1/dataset/rq2_1_sampling_metadata.json"),
    )
    parser.add_argument(
        "--max-attempt-multiplier",
        type=int,
        default=20,
        help="Retry budget multiplier used to avoid duplicate sampled documents.",
    )
    return parser.parse_args()


def load_source_overrides(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def make_source_specs(
    sources: list[str],
    source_overrides: dict[str, dict[str, Any]],
) -> dict[str, list[CollectionSpec]]:
    specs_by_source: dict[str, list[CollectionSpec]] = {}
    for source in sources:
        source_key = source.lower()
        if source_key not in SOURCE_FACTORIES:
            valid_sources = ", ".join(sorted(SOURCE_FACTORIES))
            raise ValueError(f"Unknown source '{source}'. Valid sources: {valid_sources}")
        config = source_overrides.get(source_key)
        specs_by_source[source_key] = SOURCE_FACTORIES[source_key](config)
    return specs_by_source


def source_output_path(output_dir: Path, specs: list[CollectionSpec]) -> Path:
    source_key = specs[0].source_key
    return output_dir / f"{source_key}_audit_sample.csv"


def main() -> int:
    args = parse_args()
    if MongoClient is None:
        print("pymongo is required. Install it with: pip install pymongo", file=sys.stderr)
        return 2

    source_overrides = load_source_overrides(args.source_config_json)
    specs_by_source = make_source_specs(args.sources, source_overrides)
    mongo_uri = args.mongo_uri or f"mongodb://{args.mongo_host}:{args.mongo_port}"
    rng = random.Random(args.seed)

    output_files: dict[str, str] = {}
    sampling_metadata: list[dict[str, Any]] = []

    with MongoClient(mongo_uri) as client:
        for source in args.sources:
            source_key = source.lower()
            source_rows: list[dict[str, str]] = []
            source_specs = specs_by_source[source_key]
            for sample_type, sample_size in [
                ("positive_doc", args.positive_per_source),
                ("negative_doc", args.negative_per_source),
            ]:
                sampled_rows, metadata = sample_documents(
                    client=client,
                    specs=source_specs,
                    sample_type=sample_type,
                    sample_size=sample_size,
                    rng=rng,
                    max_attempt_multiplier=args.max_attempt_multiplier,
                )
                source_rows.extend(sampled_rows)
                sampling_metadata.extend(metadata)
                if len(sampled_rows) < sample_size:
                    print(
                        (
                            f"Warning: sampled {len(sampled_rows)}/{sample_size} rows for "
                            f"{source} {sample_type}."
                        ),
                        file=sys.stderr,
                    )
            output_path = source_output_path(args.output_dir, source_specs)
            write_csv(output_path, source_rows, source_specs[0].export_columns)
            output_files[source_key] = str(output_path)
            print(f"Wrote {len(source_rows)} rows to {output_path}")

    write_metadata(
        args.metadata_output,
        {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "seed": args.seed,
            "mongo_uri": mongo_uri,
            "sources": args.sources,
            "positive_per_source": args.positive_per_source,
            "negative_per_source": args.negative_per_source,
            "output_dir": str(args.output_dir),
            "output_files": output_files,
            "queries": sampling_metadata,
            "export_columns_by_source": {
                source: specs[0].export_columns
                for source, specs in specs_by_source.items()
            },
        },
    )

    print(f"Wrote sampling metadata to {args.metadata_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
