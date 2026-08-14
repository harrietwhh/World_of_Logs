"""Shared helpers for RQ2.1 MongoDB audit sampling."""

from __future__ import annotations

import csv
import json
import random
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


EMPTY_VALUES = [None, "", [], {}]


@dataclass(frozen=True)
class CollectionSpec:
    source_key: str
    source_label: str
    db_name: str
    collection_name: str
    doc_id_fields: list[str]
    url_fields: list[str]
    created_fields: list[str]
    log_fields: list[str]
    uncertainty_fields: list[str]
    export_columns: list[str]
    metadata_fields: dict[str, list[str]] = field(default_factory=dict)
    json_fields: set[str] = field(default_factory=set)
    created_since: str | None = None
    positive_match: dict[str, Any] | None = None
    negative_match: dict[str, Any] | None = None


def field_exists_expr(field_names: list[str]) -> dict[str, Any]:
    return {
        "$or": [
            {name: {"$exists": True, "$nin": EMPTY_VALUES}}
            for name in field_names
        ]
    }


def field_missing_expr(field_names: list[str]) -> dict[str, Any]:
    return {
        "$and": [
            {"$or": [{name: {"$exists": False}}, {name: {"$in": EMPTY_VALUES}}]}
            for name in field_names
        ]
    }


def created_since_expr(field_names: list[str], created_since: str) -> dict[str, Any]:
    since_dt = datetime.fromisoformat(created_since).replace(tzinfo=timezone.utc)
    clauses = []
    for field_name in field_names:
        clauses.extend(
            [
                {field_name: {"$type": "date", "$gte": since_dt}},
                {field_name: {"$type": "string", "$gte": created_since}},
            ]
        )
    return {"$or": clauses}


def build_match(spec: CollectionSpec, sample_type: str) -> dict[str, Any]:
    clauses: list[dict[str, Any]] = []
    if sample_type == "positive_doc":
        clauses.append(spec.positive_match or field_exists_expr(spec.log_fields))
    elif sample_type == "negative_doc":
        clauses.append(spec.negative_match or field_missing_expr(spec.log_fields))
    else:
        raise ValueError(f"Unknown sample_type: {sample_type}")

    if spec.created_since:
        clauses.append(created_since_expr(spec.created_fields, spec.created_since))

    return {"$and": clauses} if len(clauses) > 1 else clauses[0]


def build_projection(spec: CollectionSpec) -> dict[str, int]:
    fields = set(
        spec.doc_id_fields
        + spec.url_fields
        + spec.created_fields
        + spec.log_fields
        + spec.uncertainty_fields
    )
    for source_fields in spec.metadata_fields.values():
        fields.update(source_fields)
    return {field_name: 1 for field_name in fields}


def get_field_value(doc: dict[str, Any], field_name: str) -> Any:
    return get_nested_value(doc, field_name.split("."))


def get_nested_value(value: Any, parts: list[str]) -> Any:
    if not parts:
        return value
    if isinstance(value, list):
        values = []
        for item in value:
            item_value = get_nested_value(item, parts)
            if item_value not in (None, "", [], {}):
                values.append(item_value)
        return values
    part = parts[0]
    if isinstance(value, dict) and part in value:
        return get_nested_value(value[part], parts[1:])
    return ""


def first_value(doc: dict[str, Any], fields: list[str]) -> Any:
    for field_name in fields:
        value = get_field_value(doc, field_name)
        if value not in (None, "", [], {}):
            return value
    return ""


def first_log_value(doc: dict[str, Any], fields: list[str]) -> Any:
    for field_name in fields:
        value = get_field_value(doc, field_name)
        if value in (None, "", [], {}, "NO_BLKS"):
            continue
        return value
    return ""


def compact_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        if not value:
            return ""
        if all(not isinstance(item, (dict, list)) for item in value):
            return "; ".join(str(item) for item in value)
        return json.dumps(value, ensure_ascii=False, default=str)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def json_value(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    return json.dumps(value, ensure_ascii=False, default=str)


def pick_log_block(doc: dict[str, Any], log_fields: list[str]) -> str:
    value = first_log_value(doc, log_fields)
    if isinstance(value, list):
        if not value:
            return ""
        first_item = value[0]
        if isinstance(first_item, dict):
            for key in ["log_blks", "log_block", "content", "text", "message", "log"]:
                if first_item.get(key) and first_item.get(key) != "NO_BLKS":
                    return compact_value(first_item[key])
        return compact_value(first_item)
    return compact_value(value)


def normalize_row(
    doc: dict[str, Any],
    spec: CollectionSpec,
    sample_type: str,
    sample_number: int,
) -> dict[str, str]:
    sample_source = spec.source_label.lower().replace(" ", "_")
    row = {
        "sample_id": f"{sample_source}_{sample_type}_{sample_number:04d}",
        "source": spec.source_label,
        "sample_type": sample_type,
        "doc_id": compact_value(first_value(doc, spec.doc_id_fields)),
        "url": compact_value(first_value(doc, spec.url_fields)),
        "created_at": compact_value(first_value(doc, spec.created_fields)),
        "pred_uncertainty": compact_value(first_value(doc, spec.uncertainty_fields)),
        "log_block": pick_log_block(doc, spec.log_fields),
    }
    for output_column, field_names in spec.metadata_fields.items():
        value = first_value(doc, field_names)
        row[output_column] = (
            json_value(value) if output_column in spec.json_fields else compact_value(value)
        )
    return row


def dedupe_key(row: dict[str, str]) -> tuple[str, str]:
    return (row.get("doc_id") or "", row.get("url") or "")


def weighted_choice(
    rng: random.Random,
    items: list[tuple[CollectionSpec, int]],
) -> CollectionSpec:
    total = sum(weight for _, weight in items)
    pick = rng.randrange(total)
    upto = 0
    for item, weight in items:
        upto += weight
        if pick < upto:
            return item
    return items[-1][0]


def sample_documents(
    client: Any,
    specs: list[CollectionSpec],
    sample_type: str,
    sample_size: int,
    rng: random.Random,
    max_attempt_multiplier: int,
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    counts: list[tuple[CollectionSpec, int]] = []
    metadata: list[dict[str, Any]] = []

    for spec in specs:
        match = build_match(spec, sample_type)
        projection = build_projection(spec)
        print(
            f"Counting {spec.source_key}/{spec.collection_name} {sample_type}...",
            file=sys.stderr,
            flush=True,
        )
        collection = client[spec.db_name][spec.collection_name]
        if sample_type == "negative_doc" and not spec.created_since:
            positive_match = build_match(spec, "positive_doc")
            total_estimated = collection.estimated_document_count()
            positive_count = collection.count_documents(positive_match)
            count = max(total_estimated - positive_count, 0)
            print(
                (
                    f"Estimated negative count via total-positive: "
                    f"{total_estimated} - {positive_count} = {count}"
                ),
                file=sys.stderr,
                flush=True,
            )
        else:
            count = collection.count_documents(match)
        print(
            f"Counted {count} matching docs in {spec.source_key}/{spec.collection_name} {sample_type}.",
            file=sys.stderr,
            flush=True,
        )
        counts.append((spec, count))
        metadata.append(
            {
                "source": spec.source_key,
                "db": spec.db_name,
                "collection": spec.collection_name,
                "sample_type": sample_type,
                "count": count,
                "query": match,
                "projection": projection,
            }
        )

    available = [(spec, count) for spec, count in counts if count > 0]
    if not available:
        return [], metadata

    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    attempts = 0
    max_attempts = max(sample_size * max_attempt_multiplier, sample_size)

    while len(rows) < sample_size and attempts < max_attempts:
        attempts += 1
        spec = weighted_choice(rng, available)
        count = next(weight for item, weight in available if item == spec)
        offset = rng.randrange(count)
        match = build_match(spec, sample_type)
        projection = build_projection(spec)
        if attempts == 1 or attempts % 10 == 0:
            print(
                (
                    f"Sampling {spec.source_key}/{spec.collection_name} {sample_type} "
                    f"attempt {attempts}/{max_attempts}; collected {len(rows)}/{sample_size}."
                ),
                file=sys.stderr,
                flush=True,
            )
        cursor = (
            client[spec.db_name][spec.collection_name]
            .find(match, projection)
            .skip(offset)
            .limit(1)
        )
        doc = next(cursor, None)
        if doc is None:
            continue
        row = normalize_row(doc, spec, sample_type, len(rows) + 1)
        key = dedupe_key(row)
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
        if len(rows) == sample_size or len(rows) % 10 == 0:
            print(
                f"Sampled {len(rows)}/{sample_size} rows for {spec.source_key} {sample_type}.",
                file=sys.stderr,
                flush=True,
            )

    return rows, metadata


def write_csv(path: Any, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_metadata(path: Any, metadata: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2, default=str)
        f.write("\n")
