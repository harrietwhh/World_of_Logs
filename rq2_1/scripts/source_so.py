"""Stack Overflow-specific RQ2.1 sampling configuration."""

from __future__ import annotations

from typing import Any

from utils import CollectionSpec


SOURCE_KEY = "so"
SOURCE_LABEL = "Stack Overflow"

DEFAULT_CONFIG = {
    "db": "SO_v2",
    "collections": ["SO_v2"],
    "created_since": "2025-07-01",
}

EXPORT_COLUMNS = [
    "sample_id",
    "source",
    "sample_type",
    "doc_id",
    "url",
    "tag",
    "created_at",
    "pred_uncertainty",
    "has_log_msg_desc",
    "has_log_msg_comm",
    "log_blks",
    "log_blks_answers",
    "question_description",
    "answer_descriptions",
]

POSITIVE_MATCH = {
    "$or": [
        {"has_log_msg_desc": True},
        {"has_log_msg_comm": True},
    ]
}

NEGATIVE_MATCH = {
    "$and": [
        {
            "$or": [
                {"has_log_msg_desc": {"$exists": False}},
                {"has_log_msg_desc": {"$ne": True}},
            ]
        },
        {
            "$or": [
                {"has_log_msg_comm": {"$exists": False}},
                {"has_log_msg_comm": {"$ne": True}},
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
            doc_id_fields=["id", "key", "_id"],
            url_fields=["unique_url"],
            created_fields=["created_at", "fields.created"],
            log_fields=["log_blks", "log_blks_answers"],
            uncertainty_fields=["pred_uncertainty"],
            export_columns=EXPORT_COLUMNS,
            metadata_fields={
                "tag": ["fields.tags"],
                "has_log_msg_desc": ["has_log_msg_desc"],
                "has_log_msg_comm": ["has_log_msg_comm"],
                "log_blks": ["log_blks"],
                "log_blks_answers": ["log_blks_answers"],
                "question_description": ["fields.description"],
                "answer_descriptions": ["answers.description"],
            },
            json_fields={"log_blks_answers", "answer_descriptions"},
            created_since=config.get("created_since"),
            positive_match=POSITIVE_MATCH,
            negative_match=NEGATIVE_MATCH,
        )
        for collection in config["collections"]
    ]
