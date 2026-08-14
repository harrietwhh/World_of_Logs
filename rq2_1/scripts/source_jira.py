"""JIRA-specific RQ2.1 sampling configuration."""

from __future__ import annotations

from typing import Any

from utils import CollectionSpec


SOURCE_KEY = "jira"
SOURCE_LABEL = "JIRA"

DEFAULT_COLLECTIONS = [
    "Apache",
    "Jira",
    "JiraEcosystem",
    "MariaDB",
    "MongoDB",
    "Qt",
    "RedHat",
    "Sakai",
]

DEFAULT_CONFIG = {
    "db": "JiraRepos_crawl_v2",
    "collections": DEFAULT_COLLECTIONS,
    "created_since": "2022-01-06",
}

EXPORT_COLUMNS = [
    "sample_id",
    "source",
    "sample_type",
    "doc_id",
    "url",
    "project",
    "issue_key",
    "created_at",
    "pred_uncertainty",
    "has_log_msg_desc",
    "has_log_msg_comm",
    "log_blks",
    "log_blks_comments",
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
            doc_id_fields=["key", "id", "doc_id", "issue_id", "_id"],
            url_fields=["unique_url", "url", "self", "link"],
            created_fields=["created_at"],
            log_fields=["log_blks", "log_blks_comments"],
            uncertainty_fields=["pred_uncertainty", "uncertainty", "avg_pred_uncertainty"],
            export_columns=EXPORT_COLUMNS,
            metadata_fields={
                "project": ["source.project"],
                "issue_key": ["key"],
                "has_log_msg_desc": ["has_log_msg_desc"],
                "has_log_msg_comm": ["has_log_msg_comm"],
                "log_blks": ["log_blks"],
                "log_blks_comments": ["log_blks_comments"],
                "issue_description": ["fields.description"],
                "comment_bodies": ["fields.comments.body"],
            },
            json_fields={"log_blks_comments", "comment_bodies"},
            created_since=config.get("created_since"),
            positive_match=POSITIVE_MATCH,
            negative_match=NEGATIVE_MATCH,
        )
        for collection in config["collections"]
    ]
