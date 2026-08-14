#!/usr/bin/env python3
import json
import re
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

try:
    from loguru import logger
except ImportError:
    import logging

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger = logging.getLogger(__name__)


EXTERNAL_CONTEXT_HEADER = "External background from internet retrieval (for reference only):"

# Current usage in this directory:
# - Enabled by default: deterministic retrieval helpers such as
#   `_search_origin_doc_ids`, `build_input_text`, and `_fetch_descriptions_from_mongo`
# - Not enabled by default: the copied LLM summarization / final external-context path below
#
# Enable the legacy LLM path only when all of the following are true:
# - you want fully automatic relevance filtering inside project code
# - the local Azure OpenAI `api_router.py` is correctly configured
# - required API/model access is available
# - you intentionally prefer automated summarization over manual review of raw candidates


@dataclass
class ExternalContextConfig:
    enable_external_context: bool = True
    search_api_url: str = ""
    mongo_uri: str = ""
    mongo_db: str = ""
    mongo_collection: str = ""
    search_timeout_sec: int = 8
    external_context_max_desc: int = 10
    external_context_keep_topn: int = 3
    external_context_desc_max_len: int = 512


def _get_config_value(config, key, default=None):
    if isinstance(config, dict):
        return config.get(key, default)
    return getattr(config, key, default)


def _extract_origin_doc_ids(payload):
    doc_ids = []

    def walk(obj):
        if isinstance(obj, dict):
            metadata = obj.get("metadata")
            if isinstance(metadata, dict) and "origin_doc_id" in metadata:
                doc_ids.append(str(metadata["origin_doc_id"]))
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(payload)
    dedup = []
    seen = set()
    for doc_id in doc_ids:
        if doc_id and doc_id not in seen:
            seen.add(doc_id)
            dedup.append(doc_id)
    return dedup


def _normalize_text(value):
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip()


def _truncate_text_by_words(text, max_words):
    if max_words is None or max_words <= 0:
        return str(text).strip()

    tokens = re.findall(r"\S+|\s+", str(text))
    kept = []
    word_count = 0
    for token in tokens:
        if token.isspace():
            if kept:
                kept.append(token)
            continue
        if word_count >= max_words:
            break
        kept.append(token)
        word_count += 1
    return "".join(kept).strip()


def _search_origin_doc_ids(search_api_url, query, timeout_sec=8):
    url = f"{search_api_url}?{urlencode({'query': query})}"
    logger.info(
        f"[extctx] Search API start: timeout={timeout_sec}s, query_chars={len(str(query))}"
    )
    try:
        with urlopen(url, timeout=timeout_sec) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        doc_ids = _extract_origin_doc_ids(data)
        logger.info(f"[extctx] Search API done: extracted_origin_doc_ids={len(doc_ids)}")
        return doc_ids
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        logger.warning(
            f"Search API request failed for query '{_truncate_text_by_words(query, 256)}': {exc}"
        )
        return []


def build_input_text(doc, prefer_title_over_summary=True, include_both_title_and_summary=False):
    if not isinstance(doc, dict):
        return ""

    fields = doc.get("fields")
    fields = fields if isinstance(fields, dict) else {}

    title = _normalize_text(fields.get("title"))
    summary = _normalize_text(fields.get("summary"))
    description = _normalize_text(fields.get("description"))

    header_texts = []
    if include_both_title_and_summary:
        ordered = [("Title", title), ("Summary", summary)]
        if not prefer_title_over_summary:
            ordered = [("Summary", summary), ("Title", title)]
        for label, text in ordered:
            if text:
                header_texts.append((label, text))
    else:
        if prefer_title_over_summary:
            primary = ("Title", title) if title else ("Summary", summary)
        else:
            primary = ("Summary", summary) if summary else ("Title", title)
        if primary[1]:
            header_texts.append(primary)

    comments = doc.get("comments")
    answers = doc.get("answers")
    comment_lines = []
    answer_lines = []

    if isinstance(comments, list):
        for item in comments:
            if not isinstance(item, dict):
                continue
            action = item.get("action")
            if action is not None and str(action).strip().lower() == "opened":
                continue
            body = _normalize_text(item.get("body"))
            if body:
                comment_lines.append(body)

    if isinstance(answers, list):
        for item in answers:
            if not isinstance(item, dict):
                continue
            answer_desc = _normalize_text(item.get("description"))
            if answer_desc:
                answer_lines.append(answer_desc)

    segments = []
    for label, text in header_texts:
        segments.append(f"{label}:\n{text}")
    if description:
        segments.append(f"Description:\n{description}")
    if comment_lines:
        comment_block = "\n".join(f"- {line}" for line in comment_lines)
        segments.append(f"Comments:\n{comment_block}")
    elif answer_lines:
        answer_block = "\n".join(f"- {line}" for line in answer_lines)
        segments.append(f"Answers:\n{answer_block}")

    return "\n\n".join(segment for segment in segments if _normalize_text(segment))


def _fetch_descriptions_from_mongo(origin_doc_ids, mongo_uri, mongo_db, mongo_collection, max_desc=10):
    if not origin_doc_ids:
        logger.info("[extctx] MongoDB retrieval skipped: no origin_doc_ids")
        return []
    try:
        from pymongo import MongoClient
    except Exception as exc:
        logger.warning(f"pymongo is unavailable, skip external context: {exc}")
        return []

    descriptions = []
    client = None
    try:
        logger.info(
            f"[extctx] MongoDB retrieval start: db={mongo_db}, collection={mongo_collection}, "
            f"candidate_ids={len(origin_doc_ids)}, max_desc={max_desc}"
        )
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        collection = client[mongo_db][mongo_collection]
        for doc_id in origin_doc_ids:
            if len(descriptions) >= max_desc:
                break
            doc = collection.find_one(
                {"_id": doc_id},
                {
                    "fields.title": 1,
                    "fields.summary": 1,
                    "fields.description": 1,
                    "comments.body": 1,
                    "comments.action": 1,
                    "answers.description": 1,
                },
            )
            if not doc:
                logger.debug(f"[extctx] MongoDB miss: _id={doc_id}")
                continue
            input_text = build_input_text(doc)
            if input_text:
                descriptions.append(input_text)
            else:
                logger.debug(f"[extctx] MongoDB empty input_text after filtering: _id={doc_id}")
    except Exception as exc:
        logger.warning(f"MongoDB query failed: {exc}")
        return []
    finally:
        if client is not None:
            client.close()

    dedup = []
    seen = set()
    for desc in descriptions:
        if desc not in seen:
            seen.add(desc)
            dedup.append(desc)
    logger.info(
        f"[extctx] MongoDB retrieval done: raw_candidate_texts={len(descriptions)}, deduped={len(dedup)}"
    )
    return dedup


def _extract_fenced_json(text):
    if not isinstance(text, str):
        return text
    match = re.search(r"```json\s*(.*?)\s*```", text, re.S | re.I)
    if match:
        return match.group(1).strip()
    match = re.search(r"```\s*(.*?)\s*```", text, re.S)
    if match:
        return match.group(1).strip()
    return text.strip()
