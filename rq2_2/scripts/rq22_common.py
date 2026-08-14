"""Shared helpers for RQ2.2 four-month figure-data scripts."""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

try:
    from pymongo import MongoClient
except ImportError:  # pragma: no cover - handled at runtime for user clarity
    MongoClient = None


SOURCE_ORDER = ["jira", "github", "so", "cc"]
DOC_ID_FIELDS = ["_id", "unique_url"]
LOG_FIELDS = [
    "has_log_msg",
    "has_log_msg_desc",
    "has_log_msg_comm",
    "log_msg_count",
    "log_msg_count_desc",
    "log_msg_count_comm",
]


@dataclass(frozen=True)
class SourceSpec:
    key: str
    label: str
    db: str | None
    collections: list[str] | None
    entity_type: str
    entity_fields: list[str]


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--uri",
        default="mongodb://127.0.0.1:27017",
        help="MongoDB URI.",
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        default=None,
        help=(
            "Sources to include: jira, github, so, cc. "
            "If omitted, sources are inferred from the provided --*-db arguments."
        ),
    )
    parser.add_argument("--jira-db")
    parser.add_argument("--jira-colls", nargs="+")
    parser.add_argument("--github-db")
    parser.add_argument("--github-colls", nargs="+")
    parser.add_argument("--so-db")
    parser.add_argument("--so-colls", nargs="+")
    parser.add_argument("--cc-db")
    parser.add_argument("--cc-colls", nargs="+")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("RQ2_2/results/figure_data"),
        help="Directory for CSV and metadata outputs.",
    )
    parser.add_argument(
        "--window-months",
        type=int,
        default=4,
        help="Release-window length in months. RQ2.2 uses 4.",
    )
    parser.add_argument(
        "--window-anchor-month",
        type=int,
        default=1,
        help="First month of the first yearly window. Default 1 gives Jan/May/Sep.",
    )
    parser.add_argument(
        "--start-date",
        default="2021-01-01",
        help="Inclusive created_at lower bound in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--end-date",
        default="2026-01-01",
        help="Exclusive created_at upper bound in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--limit-per-collection",
        type=int,
        default=None,
        help="Debug option: limit documents read from each collection.",
    )


def build_source_specs(args: argparse.Namespace) -> dict[str, SourceSpec]:
    return {
        "jira": SourceSpec(
            key="jira",
            label="JIRA",
            db=args.jira_db,
            collections=args.jira_colls,
            entity_type="project",
            entity_fields=["fields.project.name"],
        ),
        "github": SourceSpec(
            key="github",
            label="GitHub",
            db=args.github_db,
            collections=args.github_colls,
            entity_type="repository",
            entity_fields=["fields.repo", "repo", "repository", "repo_name", "full_name", "key"],
        ),
        "so": SourceSpec(
            key="so",
            label="Stack Overflow",
            db=args.so_db,
            collections=args.so_colls,
            entity_type="tag",
            entity_fields=["fields.tags"],
        ),
        "cc": SourceSpec(
            key="cc",
            label="Common Crawl",
            db=args.cc_db,
            collections=args.cc_colls,
            entity_type="domain",
            entity_fields=["domain", "host", "hostname", "source.domain", "unique_url", "url", "key"],
        ),
    }


def selected_source_keys(args: argparse.Namespace, specs: dict[str, SourceSpec]) -> list[str]:
    aliases = {"stack_overflow": "so", "common_crawl": "cc"}
    if args.sources is None:
        selected = [source_key for source_key in SOURCE_ORDER if specs[source_key].db]
    else:
        selected = [aliases.get(source.lower(), source.lower()) for source in args.sources]
    unknown_sources = sorted(set(selected) - set(specs))
    if unknown_sources:
        raise ValueError(f"Unknown sources: {unknown_sources}")
    if not selected:
        raise ValueError(
            "No sources selected. Pass --sources or provide at least one --*-db argument."
        )
    return selected


def validate_source_specs(specs: dict[str, SourceSpec], selected_sources: list[str]) -> None:
    missing = []
    for source_key in selected_sources:
        spec = specs[source_key]
        if not spec.db:
            missing.append(f"--{source_key}-db")
        if not spec.collections:
            missing.append(f"--{source_key}-colls")
    if missing:
        raise ValueError(f"Missing required arguments for selected sources: {', '.join(missing)}")


def get_nested_parts(value: Any, parts: list[str]) -> Any:
    if not parts:
        return value
    if isinstance(value, list):
        values = []
        for item in value:
            item_value = get_nested_parts(item, parts)
            if item_value not in (None, "", [], {}):
                if isinstance(item_value, list):
                    values.extend(item_value)
                else:
                    values.append(item_value)
        return values
    if isinstance(value, dict) and parts[0] in value:
        return get_nested_parts(value[parts[0]], parts[1:])
    return None


def get_nested_value(value: Any, field_name: str) -> Any:
    return get_nested_parts(value, field_name.split("."))


def first_value(doc: dict[str, Any], fields: list[str]) -> Any:
    for field_name in fields:
        value = get_nested_value(doc, field_name)
        if value not in (None, "", [], {}):
            return value
    return None


def parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        timestamp = value / 1000 if value > 10_000_000_000 else value
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.startswith("ISODate("):
            text = text.removeprefix("ISODate(").removesuffix(")").strip("\"'")
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    else:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_date_bound(value: str, arg_name: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{arg_name} must use YYYY-MM-DD or ISO datetime format.") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def release_window(dt: datetime, window_months: int, anchor_month: int) -> tuple[str, str, str]:
    if not 1 <= anchor_month <= 12:
        raise ValueError("--window-anchor-month must be between 1 and 12")
    if not 1 <= window_months <= 12:
        raise ValueError("--window-months must be between 1 and 12")

    month_index = (dt.month - anchor_month) % 12
    start_month = ((dt.month - 1 - month_index % window_months) % 12) + 1
    start_year = dt.year - int(start_month > dt.month)
    end_month_number = start_month + window_months - 1
    end_year = start_year + (end_month_number - 1) // 12
    end_month = ((end_month_number - 1) % 12) + 1

    start = f"{start_year:04d}-{start_month:02d}"
    end = f"{end_year:04d}-{end_month:02d}"
    return f"{start}_to_{end}", start, end


def is_nonempty_log_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() not in {"", "NO_BLKS"}
    if isinstance(value, list):
        return any(is_nonempty_log_value(item) for item in value)
    if isinstance(value, dict):
        if "log_blks" in value:
            return is_nonempty_log_value(value["log_blks"])
        if "text" in value:
            return is_nonempty_log_value(value["text"])
        return any(is_nonempty_log_value(item) for item in value.values())
    return True


def count_log_values(value: Any) -> int:
    if not is_nonempty_log_value(value):
        return 0
    if isinstance(value, list):
        return sum(count_log_values(item) for item in value)
    if isinstance(value, dict):
        if "log_blks" in value:
            return count_log_values(value["log_blks"])
        if "text" in value:
            return count_log_values(value["text"])
    return 1


class MissingLogCountError(ValueError):
    """Raised when a document has no usable numeric log count fields."""


def infer_log_metrics(doc: dict[str, Any]) -> tuple[bool, int]:
    has_log = any(
        get_nested_value(doc, field_name) is True
        for field_name in ["has_log_msg", "has_log_msg_desc", "has_log_msg_comm"]
    )
    if not has_log:
        return False, 0

    counts = []
    for field_name in ["log_msg_count", "log_msg_count_desc", "log_msg_count_comm"]:
        value = get_nested_value(doc, field_name)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            counts.append(int(value))

    if get_nested_value(doc, "log_msg_count") not in (None, ""):
        if not counts:
            raise MissingLogCountError(
                "Document has no usable numeric log count fields: "
                "log_msg_count, log_msg_count_desc, log_msg_count_comm"
            )
        num_logs = max(counts)
    elif counts:
        num_logs = sum(counts)
    else:
        raise MissingLogCountError(
            "Document has no usable numeric log count fields: "
            "log_msg_count, log_msg_count_desc, log_msg_count_comm"
        )

    return has_log or num_logs > 0, num_logs


def normalize_entities(source_key: str, raw_value: Any) -> list[str]:
    if raw_value is None or raw_value == "" or raw_value == [] or raw_value == {}:
        return []
    if isinstance(raw_value, list):
        entities = []
        for item in raw_value:
            entities.extend(normalize_entities(source_key, item))
        return sorted(set(entities))
    if isinstance(raw_value, dict):
        for key in ["key", "name", "full_name", "repo", "domain", "host"]:
            if raw_value.get(key):
                return normalize_entities(source_key, raw_value[key])
        return []

    text = str(raw_value).strip()
    if not text:
        return []
    if source_key == "cc":
        parsed = urlparse(text)
        return [parsed.netloc.lower()] if parsed.netloc else [text.lower()]
    if source_key == "jira" and "/" not in text and "-" in text:
        return [text.split("-", 1)[0]]
    return [text]


def projection_for(spec: SourceSpec, include_entities: bool = True) -> dict[str, int]:
    fields = set(DOC_ID_FIELDS + LOG_FIELDS + ["created_at"])
    if include_entities:
        fields.update(spec.entity_fields)
    return {field_name: 1 for field_name in fields}


def iter_source_docs(
    client: Any,
    spec: SourceSpec,
    limit_per_collection: int | None,
    start_date: datetime,
    end_date: datetime,
    include_entities: bool = True,
) -> Iterator[tuple[str, dict[str, Any]]]:
    if spec.db is None or spec.collections is None:
        raise ValueError(f"Source {spec.key} is missing db or collections.")

    for collection_name in spec.collections:
        collection = client[spec.db][collection_name]
        with client.start_session() as session:
            cursor = collection.find(
                {"created_at": {"$gte": start_date, "$lt": end_date}},
                projection_for(spec, include_entities=include_entities),
                no_cursor_timeout=True,
                session=session,
            ).sort("created_at", 1)
            if limit_per_collection:
                cursor = cursor.limit(limit_per_collection)
            try:
                for doc in cursor:
                    yield collection_name, doc
            finally:
                cursor.close()


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def make_run_output_dir(base_dir: Path, run_name: str, sources: list[str]) -> Path:
    source_part = "-".join(sources)
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    run_dir = base_dir / f"{run_name}_{source_part}_{timestamp}"
    # suffix = 1
    # while run_dir.exists():
    #     suffix += 1
    #     run_dir = base_dir / f"{run_name}_{source_part}_{timestamp}_{suffix}"
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def fmt_float(value: float | None) -> str:
    if value is None or math.isnan(value):
        return ""
    return f"{value:.6f}"


def require_pymongo() -> None:
    if MongoClient is None:
        raise RuntimeError("pymongo is required. Install it with: pip install pymongo")
