#!/usr/bin/env python3
import argparse
import ast
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

try:
    from loguru import logger
except ImportError:
    import logging

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger = logging.getLogger(__name__)

from external_context_rag import _fetch_descriptions_from_mongo
from external_context_rag import _search_origin_doc_ids


DEFAULT_SEARCH_API_URL = "http://129.97.92.71:8000/api/search"
DEFAULT_MONGO_URI = "mongodb://127.0.0.1:27017"
DEFAULT_MONGO_DB = "WoL_v2"
DEFAULT_MONGO_COLLECTION = "WoL_v2"


def _normalize_space(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _slugify_for_path(text, max_len=80):
    normalized = re.sub(r"\s+", "_", str(text).strip().lower())
    normalized = re.sub(r"[^a-z0-9_]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    if not normalized:
        normalized = "query"
    return normalized[:max_len].rstrip("_") or "query"


def _build_output_dir(base_dir, output_dir, output_label):
    if output_dir:
        return Path(output_dir)

    slug = _slugify_for_path(output_label)
    return base_dir / "intermediate" / slug


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_case_from_csv(cases_csv, case_id):
    case_id = str(case_id)
    with Path(cases_csv).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if str(row.get("case_id", "")).strip() != case_id:
                continue

            summary_raw = row.get("summary", "")
            try:
                parsed_summary = ast.literal_eval(summary_raw) if summary_raw else []
            except (ValueError, SyntaxError):
                parsed_summary = [summary_raw]

            if isinstance(parsed_summary, str):
                parsed_summary = [parsed_summary]
            elif not isinstance(parsed_summary, list):
                parsed_summary = [str(parsed_summary)]

            summary_items = [_normalize_space(item) for item in parsed_summary if _normalize_space(item)]
            group_logs = row.get("group_logs", "")
            return {
                "case_id": case_id,
                "group_logs": group_logs,
                "group_logs_lines": [line for line in group_logs.splitlines() if line.strip()],
                "summary_items": summary_items,
                "summary_raw": summary_raw,
            }

    raise ValueError(f"Case ID not found in {cases_csv}: {case_id}")


_MULTI_DOTS_RE = re.compile(r"\.{2,}")
_PUNCT_SPACE_RE = re.compile(r"\s*:\s*")
_SPACE_COMMA_RE = re.compile(r"\s+,")


def _compact_log_line(raw_line):
    line = _normalize_space(raw_line)
    if not line:
        return ""

    line = _MULTI_DOTS_RE.sub(" ", line)
    line = _PUNCT_SPACE_RE.sub(": ", line)
    line = _SPACE_COMMA_RE.sub(",", line)
    line = re.sub(r"\s+", " ", line).strip(" .")
    return line


def build_query_from_raw_group_logs(group_logs):
    lines = []
    seen = set()
    for raw_line in str(group_logs or "").splitlines():
        line = _normalize_space(raw_line)
        if not line or line in seen:
            continue
        seen.add(line)
        lines.append(line)
    return lines


def build_query_from_group_logs(group_logs):
    counts = {}
    ordered = []

    for raw_line in str(group_logs or "").splitlines():
        compact = _compact_log_line(raw_line)
        if not compact:
            continue
        counts[compact] = counts.get(compact, 0) + 1
        if compact not in ordered:
            ordered.append(compact)

    ordered.sort(key=lambda item: (-counts[item], -len(item), item))

    queries = []
    seen = set()
    for query in ordered:
        normalized = _normalize_space(query)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        queries.append(normalized)
    return queries


def _resolve_queries(args):
    if args.case_id:
        case_payload = _load_case_from_csv(args.cases_csv, args.case_id)
        if args.query_source == "raw_group_logs":
            queries = build_query_from_raw_group_logs(case_payload["group_logs"])
        else:
            queries = build_query_from_group_logs(case_payload["group_logs"])

        if not queries:
            raise ValueError(f"No queries built for case_id={args.case_id} using query_source={args.query_source}")

        output_label = f"case_{case_payload['case_id']}_{args.query_source}"
        return case_payload, queries, output_label

    query = _normalize_space(args.log_message)
    if not query:
        raise ValueError("--log_message cannot be empty")
    return None, [query], query


def _run_retrieval_for_queries(queries, args):
    per_query_results = []
    merged_doc_ids = []
    merged_candidates = []
    seen_doc_ids = set()
    seen_candidates = set()

    for query in queries:
        origin_doc_ids = _search_origin_doc_ids(
            args.search_api_url,
            query,
            timeout_sec=args.search_timeout_sec,
        )
        candidates = _fetch_descriptions_from_mongo(
            origin_doc_ids,
            mongo_uri=args.mongo_uri,
            mongo_db=args.mongo_db,
            mongo_collection=args.mongo_collection,
            max_desc=args.external_context_max_desc,
        )

        per_query_results.append(
            {
                "query": query,
                "origin_doc_ids": origin_doc_ids,
                "candidates": [{"rank": idx, "text": text} for idx, text in enumerate(candidates, start=1)],
            }
        )

        for doc_id in origin_doc_ids:
            if doc_id not in seen_doc_ids:
                seen_doc_ids.add(doc_id)
                merged_doc_ids.append(doc_id)

        for candidate in candidates:
            if candidate not in seen_candidates:
                seen_candidates.add(candidate)
                merged_candidates.append(candidate)

    return per_query_results, merged_doc_ids, merged_candidates


def _write_markdown(path, query_label, per_query_results, merged_doc_ids, merged_candidates):
    lines = [
        "# Retrieved RAG Candidates",
        "",
        "## Query Label",
        "",
        query_label,
        "",
        "## Per-Query Retrieval",
        "",
    ]

    if per_query_results:
        for idx, result in enumerate(per_query_results, start=1):
            lines.extend(
                [
                    f"### Query {idx}",
                    "",
                    "```text",
                    result["query"],
                    "```",
                    "",
                    "Origin Doc IDs:",
                    "",
                ]
            )
            if result["origin_doc_ids"]:
                lines.extend([f"{rank}. `{doc_id}`" for rank, doc_id in enumerate(result["origin_doc_ids"], start=1)])
            else:
                lines.append("_No origin_doc_id retrieved for this query._")

            lines.extend(["", "Candidate Texts", ""])
            if result["candidates"]:
                for candidate in result["candidates"]:
                    lines.extend(
                        [
                            f"#### Candidate {candidate['rank']}",
                            "",
                            "```text",
                            candidate["text"],
                            "```",
                            "",
                        ]
                    )
            else:
                lines.append("_No candidate texts retrieved from MongoDB for this query._")
    else:
        lines.append("_No queries were executed._")

    lines.extend(["", "## Merged Origin Doc IDs", ""])
    if merged_doc_ids:
        lines.extend([f"{idx}. `{doc_id}`" for idx, doc_id in enumerate(merged_doc_ids, start=1)])
    else:
        lines.append("_No merged origin_doc_id retrieved._")

    lines.extend(["", "## Merged Candidate Texts", ""])
    if merged_candidates:
        for idx, candidate in enumerate(merged_candidates, start=1):
            lines.extend(
                [
                    f"### Candidate {idx}",
                    "",
                    "```text",
                    candidate,
                    "```",
                    "",
                ]
            )
    else:
        lines.append("_No merged candidate texts retrieved from MongoDB._")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run deterministic RAG retrieval for a case-study log message."
    )
    parser.add_argument(
        "--log_message",
        default="",
        help="Legacy single retrieval query. Use this or provide --cases_csv plus --case_id.",
    )
    parser.add_argument(
        "--cases_csv",
        default="data/bgl.csv",
        help="Path to a case CSV with case_id, group_logs, and summary columns.",
    )
    parser.add_argument(
        "--bgl_csv",
        dest="cases_csv",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--case_id", default="", help="Case ID in the CSV to retrieve external knowledge for.")
    parser.add_argument(
        "--query_source",
        choices=["group_logs", "raw_group_logs"],
        default="group_logs",
        help="How to build retrieval queries for a case.",
    )
    parser.add_argument("--search_api_url", default=DEFAULT_SEARCH_API_URL)
    parser.add_argument("--mongo_uri", default=DEFAULT_MONGO_URI)
    parser.add_argument("--mongo_db", default=DEFAULT_MONGO_DB)
    parser.add_argument("--mongo_collection", default=DEFAULT_MONGO_COLLECTION)
    parser.add_argument("--search_timeout_sec", type=int, default=8)
    parser.add_argument("--external_context_max_desc", type=int, default=10)
    parser.add_argument(
        "--output_dir",
        default="",
        help="Directory for intermediate retrieval artifacts. Defaults to intermediate/<query_slug>.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    # Keep generated artifacts at the experiment root even though the runner
    # is organized under scripts/rag/.
    base_dir = Path(__file__).resolve().parents[2]
    if not args.case_id and not _normalize_space(args.log_message):
        raise ValueError("Provide either --log_message or --case_id with --cases_csv.")

    case_payload, queries, output_label = _resolve_queries(args)
    output_dir = _build_output_dir(base_dir, args.output_dir, output_label)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(
        f"Retrieval start: queries={len(queries)}, query_source={args.query_source}, output_dir={output_dir}"
    )
    per_query_results, origin_doc_ids, candidates = _run_retrieval_for_queries(queries, args)

    metadata = {
        "mode": "csv_case" if args.case_id else "legacy_log_message",
        "case_id": str(case_payload["case_id"]) if case_payload else "",
        "query_source": args.query_source if args.case_id else "log_message",
        "query_count": len(queries),
        "queries": queries,
        "log_message": args.log_message,
        "cases_csv": args.cases_csv,
        "search_api_url": args.search_api_url,
        "mongo_uri": args.mongo_uri,
        "mongo_db": args.mongo_db,
        "mongo_collection": args.mongo_collection,
        "search_timeout_sec": args.search_timeout_sec,
        "external_context_max_desc": args.external_context_max_desc,
        "retrieved_origin_doc_id_count": len(origin_doc_ids),
        "retrieved_candidate_count": len(candidates),
        "output_dir": str(output_dir),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    if case_payload:
        _write_json(
            output_dir / "case_input.json",
            {
                "case_id": case_payload["case_id"],
                "summary_raw": case_payload["summary_raw"],
                "summary_items": case_payload["summary_items"],
                "group_logs_lines": case_payload["group_logs_lines"],
            },
        )
    _write_json(output_dir / "retrieval_config.json", metadata)
    _write_json(output_dir / "retrieval_queries.json", per_query_results)
    _write_json(output_dir / "retrieved_doc_ids.json", origin_doc_ids)
    _write_json(
        output_dir / "retrieved_candidates.json",
        [{"rank": idx, "text": text} for idx, text in enumerate(candidates, start=1)],
    )
    _write_markdown(
        output_dir / "retrieved_candidates.md",
        output_label,
        per_query_results,
        origin_doc_ids,
        candidates,
    )

    logger.info(
        "Retrieval finished: "
        f"origin_doc_ids={len(origin_doc_ids)}, candidates={len(candidates)}, output_dir={output_dir}"
    )


if __name__ == "__main__":
    main()
