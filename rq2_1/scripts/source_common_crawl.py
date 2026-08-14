"""Common Crawl-specific RQ2.1 sampling configuration."""

from __future__ import annotations

from typing import Any

from utils import CollectionSpec


SOURCE_KEY = "cc"
SOURCE_LABEL = "Common Crawl"

DEFAULT_CONFIG = {
    "db": "CommonCrawl_v2",
    "collections": ["English"],
}

EXPORT_COLUMNS = [
    "sample_id",
    "source",
    "sample_type",
    "doc_id",
    "url",
    "created_at",
    "pred_uncertainty",
    "has_log_msg",
    "log_blks",
    "log_msgs",
    "page_description",
    "dump_version",
    "imported_at",
]

POSITIVE_MATCH = {"has_log_msg": True}

NEGATIVE_MATCH = {
    "$and": [
        {
            "$or": [
                {"has_log_msg": {"$exists": False}},
                {"has_log_msg": {"$ne": True}},
            ]
        },
        {
            "$or": [
                {"log_blks": {"$exists": False}},
                {"log_blks": {"$in": [None, "", [], {}, "NO_BLKS"]}},
            ]
        },
    ]
}


def make_specs(config: dict[str, Any] | None = None) -> list[CollectionSpec]:
    config = {**DEFAULT_CONFIG, **(config or {})}
    return [
        CollectionSpec(
            source_key=SOURCE_KEY,
            source_label=SOURCE_LABEL,
            db_name=config["db"],
            collection_name=collection,
            doc_id_fields=["_id"],
            url_fields=["unique_url"],
            created_fields=["fields.collected_at", "source.imported_at"],
            log_fields=["log_blks"],
            uncertainty_fields=["pred_uncertainty"],
            export_columns=EXPORT_COLUMNS,
            metadata_fields={
                "has_log_msg": ["has_log_msg"],
                "log_blks": ["log_blks"],
                "log_msgs": ["log_msgs"],
                "page_description": ["fields.description"],
                "dump_version": ["source.dump_version"],
                "imported_at": ["source.imported_at"],
            },
            json_fields={"log_msgs"},
            positive_match=POSITIVE_MATCH,
            negative_match=NEGATIVE_MATCH,
        )
        for collection in config["collections"]
    ]
