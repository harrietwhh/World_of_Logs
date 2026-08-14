#!/usr/bin/env python3
"""Sample Common Crawl negative documents from a separate MongoDB instance."""

from __future__ import annotations

import argparse
import random
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import source_common_crawl
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sample Common Crawl negative documents only. This is intended for the "
            "separate machine/DB that stores the CC negative pool."
        )
    )
    parser.add_argument("--mongo-uri", default=None, help="MongoDB URI.")
    parser.add_argument("--mongo-host", default="localhost", help="MongoDB host.")
    parser.add_argument("--mongo-port", type=int, default=27017, help="MongoDB port.")
    parser.add_argument("--db", default="CommonCrawl_v2", help="MongoDB database name.")
    parser.add_argument(
        "--collections",
        nargs="+",
        default=["English"],
        help="Collection(s) that contain Common Crawl negative candidates.",
    )
    parser.add_argument("--seed", type=int, default=20260505, help="Random seed.")
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("RQ2/rq2.1/dataset/audit_samples/cc_negative_patch.csv"),
    )
    parser.add_argument(
        "--metadata-output",
        type=Path,
        default=Path("RQ2/rq2.1/dataset/rq2_1_cc_negative_patch_metadata.json"),
    )
    parser.add_argument(
        "--max-attempt-multiplier",
        type=int,
        default=20,
        help="Retry budget multiplier used to avoid duplicate sampled documents.",
    )
    parser.add_argument(
        "--negative-pool-is-clean",
        action="store_true",
        help=(
            "Treat every document in the configured collection(s) as a negative "
            "candidate. Use this when the separate machine already stores only "
            "negative CC documents."
        ),
    )
    return parser.parse_args()


def make_negative_specs(args: argparse.Namespace) -> list[CollectionSpec]:
    specs = source_common_crawl.make_specs(
        {
            "db": args.db,
            "collections": args.collections,
        }
    )
    if not args.negative_pool_is_clean:
        return specs
    return [replace(spec, negative_match={"_id": {"$exists": True}}) for spec in specs]


def main() -> int:
    args = parse_args()
    if MongoClient is None:
        print("pymongo is required. Install it with: pip install pymongo", file=sys.stderr)
        return 2

    mongo_uri = args.mongo_uri or f"mongodb://{args.mongo_host}:{args.mongo_port}"
    rng = random.Random(args.seed)
    specs = make_negative_specs(args)

    with MongoClient(mongo_uri) as client:
        rows, sampling_metadata = sample_documents(
            client=client,
            specs=specs,
            sample_type="negative_doc",
            sample_size=args.sample_size,
            rng=rng,
            max_attempt_multiplier=args.max_attempt_multiplier,
        )

    write_csv(args.output, rows, specs[0].export_columns)
    write_metadata(
        args.metadata_output,
        {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "seed": args.seed,
            "mongo_uri": mongo_uri,
            "db": args.db,
            "collections": args.collections,
            "sample_type": "negative_doc",
            "sample_size": args.sample_size,
            "negative_pool_is_clean": args.negative_pool_is_clean,
            "output": str(args.output),
            "queries": sampling_metadata,
            "export_columns": specs[0].export_columns,
        },
    )

    if len(rows) < args.sample_size:
        print(
            f"Warning: sampled {len(rows)}/{args.sample_size} CC negative rows.",
            file=sys.stderr,
        )
    print(f"Wrote {len(rows)} rows to {args.output}")
    print(f"Wrote sampling metadata to {args.metadata_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
