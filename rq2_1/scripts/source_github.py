"""GitHub-specific RQ2.1 sampling configuration."""

from __future__ import annotations

from typing import Any

from utils import CollectionSpec


SOURCE_KEY = "github"
SOURCE_LABEL = "GitHub"

DEFAULT_CONFIG = {
    "db": "Github_v2",
    "collections": ["comments"],
}

EXPORT_COLUMNS = [
    "sample_id",
    "source",
    "sample_type",
    "doc_id",
    "url",
    "repo",
    "created_at",
    "pred_uncertainty",
    "has_log_msg_desc",
    "has_log_msg_comm",
    "log_blks",
    "log_blks_comments",
    "issue_title",
    "issue_description",
    "comment_bodies",
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
            doc_id_fields=["key", "_id"],
            url_fields=["unique_url"],
            created_fields=["created_at", "fields.created"],
            log_fields=["log_blks", "log_blks_comments"],
            uncertainty_fields=["pred_uncertainty"],
            export_columns=EXPORT_COLUMNS,
            metadata_fields={
                "repo": ["fields.repo"],
                "has_log_msg_desc": ["has_log_msg_desc"],
                "has_log_msg_comm": ["has_log_msg_comm"],
                "log_blks": ["log_blks"],
                "log_blks_comments": ["log_blks_comments"],
                "issue_title": ["fields.title"],
                "issue_description": ["fields.description"],
                "comment_bodies": ["comments.body"],
            },
            json_fields={"log_blks_comments", "comment_bodies"},
            positive_match=POSITIVE_MATCH,
            negative_match=NEGATIVE_MATCH,
        )
        for collection in config["collections"]
    ]
