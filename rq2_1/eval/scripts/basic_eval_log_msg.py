#!/usr/bin/env python3
"""Evaluate inferred log messages against GT log annotations."""

from __future__ import annotations

import argparse
import ast
import csv
import json
import math
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple


BLOCK_DELIMITER = "\n\n\n\n\n\n"
NO_BLOCK_VALUES = {"", "NO_BLKS", "nan", "NaN", "NULL"}
DEFAULT_RELAXED_THRESHOLD = 0.8
csv.field_size_limit(sys.maxsize)

SOURCE_CONFIG = {
    "github": {
        "input": "github_audit_sample.csv",
        "inference_text_cols": ["log_blks"],
        "inference_json_cols": ["log_blks_comments"],
        "gt_text_cols": ["gt_issue_description"],
        "gt_json_text_cols": ["gt_comment_bodies"],
        "split_non_timestamp_log_lines": True,
    },
    "cc": {
        "input": "cc_audit_sample.csv",
        "inference_text_cols": ["log_blks"],
        "inference_json_cols": [],
        "gt_text_cols": ["gt_page_description"],
        "gt_json_text_cols": [],
        "split_non_timestamp_log_lines": True,
    },
    "jira": {
        "input": "jira_audit_sample.csv",
        "inference_text_cols": ["log_blks"],
        "inference_json_cols": ["log_blks_comments"],
        "gt_text_cols": ["gt_issue_description"],
        "gt_json_text_cols": ["gt_comment_bodies"],
        "split_non_timestamp_log_lines": True,
    },
    "so": {
        "input": "so_audit_sample.csv",
        "inference_text_cols": ["log_blks"],
        "inference_json_cols": ["log_blks_answers"],
        "gt_text_cols": ["gt_question_description"],
        "gt_json_text_cols": ["gt_answer_descriptions"],
        "split_non_timestamp_log_lines": True,
    },
}

LOG_TAG_RE = re.compile(r"<log>(.*?)</log>", re.IGNORECASE | re.DOTALL)
TIMESTAMP_RE = re.compile(
    r"^\s*(\[\s*)?("
    r"(\d{4}[-/]\d{2}[-/]\d{2}[ T])|"
    r"(\d{2}[-/]\d{2}[-/]\d{2}[ T])"
    r")?\d{2}:\d{2}:\d{2}(,\d+)?(\s*\])?"
)
LOG_LINE_START_RE = re.compile(
    r"^\s*("
    r"(?:console|logger|log|message)\.[A-Za-z_]\w*\s*\(|"
    r"Schema::writeToLog\s*\(|"
    r"(?:printf|print|NSLog|Debug\.WriteLine|System\.out\.println)\s*\(|"
    r"@[\w./~-]+:[\w./~-]+:|"
    r"(?:ERROR|WARN(?:ING)?|INFO|DEBUG|TRACE|FATAL)\b"
    r")",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate log message extraction for RQ2.1 audit data."
    )
    parser.add_argument(
        "--source",
        choices=sorted(SOURCE_CONFIG),
        default="github",
        help="Dataset source to evaluate. Defaults to github.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("rq2.1/eval/data"),
        help="Directory containing joined audit sample CSVs.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("rq2.1/eval/results"),
        help="Directory for evaluation outputs.",
    )
    parser.add_argument(
        "--relaxed-threshold",
        type=float,
        default=DEFAULT_RELAXED_THRESHOLD,
        help="Minimum token-level F1 for relaxed one-to-one message matching.",
    )
    return parser.parse_args()


def is_gt_not_sure(value: str) -> bool:
    return value.strip() in {"1", "1.0", "true", "True", "TRUE", "yes", "Yes", "YES"}


def is_no_block(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if not isinstance(value, str):
        value = str(value)
    return value.strip() in NO_BLOCK_VALUES


def parse_jsonish_list(value: str) -> List[Any]:
    value = (value or "").strip()
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        try:
            parsed = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            return [value]
    if isinstance(parsed, list):
        return parsed
    return [parsed]


def split_blocks(value: str) -> List[str]:
    if is_no_block(value):
        return []
    return [block.strip() for block in value.split(BLOCK_DELIMITER) if block.strip()]


def join_blocks(blocks: Sequence[str]) -> str:
    return BLOCK_DELIMITER.join(block for block in blocks if block.strip())


def dedupe_blocks_by_normalized(blocks: Sequence[str]) -> List[str]:
    unique: List[str] = []
    seen: set[str] = set()
    for block in blocks:
        key = text_only_normalize(block)
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(block)
    return unique


def extract_inference_blocks(row: Dict[str, str], config: Dict[str, List[str]]) -> List[str]:
    blocks: List[str] = []

    for col in config["inference_text_cols"]:
        blocks.extend(split_blocks(row.get(col, "")))

    for col in config["inference_json_cols"]:
        for item in parse_jsonish_list(row.get(col, "")):
            if isinstance(item, dict):
                value = item.get("log_blks", "")
            else:
                value = item
            blocks.extend(split_blocks(value))

    return dedupe_blocks_by_normalized(blocks)


def extract_log_tag_blocks(text: str) -> List[str]:
    if not text:
        return []
    return [match.group(1).strip() for match in LOG_TAG_RE.finditer(text) if match.group(1).strip()]


def extract_gt_blocks(row: Dict[str, str], config: Dict[str, List[str]]) -> List[str]:
    blocks: List[str] = []

    for col in config["gt_text_cols"]:
        blocks.extend(extract_log_tag_blocks(row.get(col, "")))

    for col in config["gt_json_text_cols"]:
        for item in parse_jsonish_list(row.get(col, "")):
            if isinstance(item, dict):
                texts = [str(v) for v in item.values()]
            else:
                texts = [str(item)]
            for text in texts:
                blocks.extend(extract_log_tag_blocks(text))

    return dedupe_blocks_by_normalized(blocks)


def split_non_timestamp_log_lines(block_text: str) -> List[str]:
    lines = block_text.splitlines()
    messages: List[List[str]] = []
    current: List[str] = []
    start_count = 0

    for line in lines:
        if not line.strip():
            if current:
                current.append(line)
            continue
        starts_message = bool(LOG_LINE_START_RE.match(line))
        if starts_message:
            start_count += 1
            if current:
                messages.append(current)
            current = [line]
        elif current:
            current.append(line)
        else:
            current = [line]

    if current:
        messages.append(current)

    if start_count < 2:
        return [block_text.strip()]
    return ["\n".join(message).strip() for message in messages if "\n".join(message).strip()]


def extract_log_messages_from_block(
    blks_value: str,
    split_non_timestamp_lines: bool = False,
) -> List[str]:
    if not blks_value:
        return []

    blocks = [block for block in blks_value.split(BLOCK_DELIMITER) if block.strip()]
    all_messages: List[str] = []

    for block_text in blocks:
        lines = block_text.splitlines()
        current_message: List[str] = []

        found_timestamp = any(TIMESTAMP_RE.match(line) for line in lines)

        if not found_timestamp:
            if split_non_timestamp_lines:
                all_messages.extend(split_non_timestamp_log_lines(block_text))
            else:
                all_messages.append(block_text.strip())
            continue

        for line in lines:
            if TIMESTAMP_RE.match(line):
                if current_message:
                    all_messages.append("\n".join(current_message).strip())
                current_message = [line]
            else:
                current_message.append(line)
        if current_message:
            all_messages.append("\n".join(current_message).strip())

    return all_messages


def strip_empty(values: Iterable[str]) -> List[str]:
    return [value.strip() for value in values if value and value.strip()]


def text_only_normalize(value: str) -> str:
    """Keep only semantic text characters for comparison."""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(ch for ch in normalized if ch.isalnum())


def tokenize_for_relaxed_match(value: str) -> List[str]:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.findall(r"[0-9a-z]+", normalized)


def token_f1(prediction: str, gold: str) -> float:
    pred_tokens = tokenize_for_relaxed_match(prediction)
    gold_tokens = tokenize_for_relaxed_match(gold)
    if not pred_tokens or not gold_tokens:
        return 0.0
    overlap = sum((Counter(pred_tokens) & Counter(gold_tokens)).values())
    if overlap == 0:
        return 0.0
    precision = overlap / len(pred_tokens)
    recall = overlap / len(gold_tokens)
    return 2 * precision * recall / (precision + recall)


def dedupe_by_normalized(messages: Sequence[str]) -> Tuple[List[str], Dict[str, str]]:
    unique: List[str] = []
    normalized_to_original: Dict[str, str] = {}
    for message in messages:
        key = text_only_normalize(message)
        if not key:
            continue
        if key not in normalized_to_original:
            normalized_to_original[key] = message
            unique.append(message)
    return unique, normalized_to_original


def safe_div(num: int, denom: int) -> float:
    return num / denom if denom else 0.0


def relaxed_one_to_one_match(
    prediction_messages: Sequence[str],
    gold_messages: Sequence[str],
    threshold: float,
) -> Tuple[List[Dict[str, Any]], List[int], List[int]]:
    edges: List[List[Tuple[int, float]]] = []
    for pred in prediction_messages:
        pred_edges: List[Tuple[int, float]] = []
        for gold_idx, gold in enumerate(gold_messages):
            score = token_f1(pred, gold)
            if score >= threshold:
                pred_edges.append((gold_idx, score))
        pred_edges.sort(key=lambda item: item[1], reverse=True)
        edges.append(pred_edges)

    matched_pred_by_gold: Dict[int, int] = {}

    def try_match(pred_idx: int, seen_gold: set[int]) -> bool:
        for gold_idx, _score in edges[pred_idx]:
            if gold_idx in seen_gold:
                continue
            seen_gold.add(gold_idx)
            if gold_idx not in matched_pred_by_gold or try_match(
                matched_pred_by_gold[gold_idx], seen_gold
            ):
                matched_pred_by_gold[gold_idx] = pred_idx
                return True
        return False

    pred_order = sorted(
        range(len(prediction_messages)),
        key=lambda idx: max((score for _gold_idx, score in edges[idx]), default=0.0),
        reverse=True,
    )
    for pred_idx in pred_order:
        try_match(pred_idx, set())

    matched_pairs = [
        {
            "prediction_index": pred_idx,
            "gold_index": gold_idx,
            "token_f1": token_f1(prediction_messages[pred_idx], gold_messages[gold_idx]),
            "prediction": prediction_messages[pred_idx],
            "gold": gold_messages[gold_idx],
        }
        for gold_idx, pred_idx in sorted(matched_pred_by_gold.items(), key=lambda item: item[1])
    ]
    matched_prediction_indices = {pair["prediction_index"] for pair in matched_pairs}
    matched_gold_indices = {pair["gold_index"] for pair in matched_pairs}
    prediction_only_indices = [
        idx for idx in range(len(prediction_messages)) if idx not in matched_prediction_indices
    ]
    gold_only_indices = [idx for idx in range(len(gold_messages)) if idx not in matched_gold_indices]
    return matched_pairs, prediction_only_indices, gold_only_indices


def evaluate_row(
    row: Dict[str, str],
    config: Dict[str, List[str]],
    relaxed_threshold: float,
) -> Dict[str, Any]:
    inference_blocks = extract_inference_blocks(row, config)
    gt_blocks = extract_gt_blocks(row, config)
    inference_blks = join_blocks(inference_blocks)
    gt_blks = join_blocks(gt_blocks)

    split_non_timestamp_lines = bool(config.get("split_non_timestamp_log_lines"))
    inference_msgs = strip_empty(
        extract_log_messages_from_block(inference_blks, split_non_timestamp_lines)
    )
    gt_msgs = strip_empty(extract_log_messages_from_block(gt_blks, split_non_timestamp_lines))

    unique_inference_msgs, inference_norm_map = dedupe_by_normalized(inference_msgs)
    unique_gt_msgs, gt_norm_map = dedupe_by_normalized(gt_msgs)

    inference_norms = set(inference_norm_map)
    gt_norms = set(gt_norm_map)
    matched_norms = inference_norms & gt_norms
    inference_only_norms = sorted(inference_norms - gt_norms)
    gt_only_norms = sorted(gt_norms - inference_norms)
    relaxed_pairs, relaxed_inference_only_indices, relaxed_gt_only_indices = (
        relaxed_one_to_one_match(unique_inference_msgs, unique_gt_msgs, relaxed_threshold)
    )

    return {
        "sample_id": row.get("sample_id", ""),
        "source": row.get("source", ""),
        "sample_type": row.get("sample_type", ""),
        "url": row.get("url", ""),
        "gt_not_sure": row.get("gt_not_sure", ""),
        "skipped": False,
        "inference_block_count": len(inference_blocks),
        "gt_block_count": len(gt_blocks),
        "inference_msg_count": len(unique_inference_msgs),
        "gt_msg_count": len(unique_gt_msgs),
        "exact_tp": len(matched_norms),
        "exact_fp": len(inference_only_norms),
        "exact_fn": len(gt_only_norms),
        "relaxed_tp": len(relaxed_pairs),
        "relaxed_fp": len(relaxed_inference_only_indices),
        "relaxed_fn": len(relaxed_gt_only_indices),
        "tp": len(matched_norms),
        "fp": len(inference_only_norms),
        "fn": len(gt_only_norms),
        "sample_exact_match": inference_norms == gt_norms,
        "sample_relaxed_match": not relaxed_inference_only_indices and not relaxed_gt_only_indices,
        "inference_blks": inference_blks,
        "gt_blks": gt_blks,
        "inference_log_msgs": unique_inference_msgs,
        "gt_log_msgs": unique_gt_msgs,
        "inference_only_log_msgs": [inference_norm_map[key] for key in inference_only_norms],
        "gt_only_log_msgs": [gt_norm_map[key] for key in gt_only_norms],
        "relaxed_matched_log_msgs": relaxed_pairs,
        "relaxed_inference_only_log_msgs": [
            unique_inference_msgs[idx] for idx in relaxed_inference_only_indices
        ],
        "relaxed_gt_only_log_msgs": [unique_gt_msgs[idx] for idx in relaxed_gt_only_indices],
    }


def skipped_row(row: Dict[str, str]) -> Dict[str, Any]:
    return {
        "sample_id": row.get("sample_id", ""),
        "source": row.get("source", ""),
        "sample_type": row.get("sample_type", ""),
        "url": row.get("url", ""),
        "gt_not_sure": row.get("gt_not_sure", ""),
        "skipped": True,
        "inference_block_count": 0,
        "gt_block_count": 0,
        "inference_msg_count": 0,
        "gt_msg_count": 0,
        "exact_tp": 0,
        "exact_fp": 0,
        "exact_fn": 0,
        "relaxed_tp": 0,
        "relaxed_fp": 0,
        "relaxed_fn": 0,
        "tp": 0,
        "fp": 0,
        "fn": 0,
        "sample_exact_match": "",
        "sample_relaxed_match": "",
        "inference_blks": "",
        "gt_blks": "",
        "inference_log_msgs": [],
        "gt_log_msgs": [],
        "inference_only_log_msgs": [],
        "gt_only_log_msgs": [],
        "relaxed_matched_log_msgs": [],
        "relaxed_inference_only_log_msgs": [],
        "relaxed_gt_only_log_msgs": [],
    }


def json_cell(value: Any) -> str:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def write_results(rows: Sequence[Dict[str, Any]], output_csv: Path) -> None:
    fieldnames = [
        "sample_id",
        "source",
        "sample_type",
        "url",
        "gt_not_sure",
        "skipped",
        "inference_block_count",
        "gt_block_count",
        "inference_msg_count",
        "gt_msg_count",
        "exact_tp",
        "exact_fp",
        "exact_fn",
        "relaxed_tp",
        "relaxed_fp",
        "relaxed_fn",
        "tp",
        "fp",
        "fn",
        "sample_exact_match",
        "sample_relaxed_match",
        "inference_blks",
        "gt_blks",
        "inference_log_msgs",
        "gt_log_msgs",
        "inference_only_log_msgs",
        "gt_only_log_msgs",
        "relaxed_matched_log_msgs",
        "relaxed_inference_only_log_msgs",
        "relaxed_gt_only_log_msgs",
    ]
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json_cell(row.get(key, "")) for key in fieldnames})


def summarize(
    source: str,
    input_csv: Path,
    rows: Sequence[Dict[str, Any]],
    relaxed_threshold: float,
) -> Dict[str, Any]:
    evaluated = [row for row in rows if not row["skipped"]]
    skipped = [row for row in rows if row["skipped"]]
    total_exact_tp = sum(int(row["exact_tp"]) for row in evaluated)
    total_exact_fp = sum(int(row["exact_fp"]) for row in evaluated)
    total_exact_fn = sum(int(row["exact_fn"]) for row in evaluated)
    total_relaxed_tp = sum(int(row["relaxed_tp"]) for row in evaluated)
    total_relaxed_fp = sum(int(row["relaxed_fp"]) for row in evaluated)
    total_relaxed_fn = sum(int(row["relaxed_fn"]) for row in evaluated)
    exact_matches = sum(1 for row in evaluated if row["sample_exact_match"])
    relaxed_matches = sum(1 for row in evaluated if row["sample_relaxed_match"])

    return {
        "source": source,
        "input_csv": str(input_csv),
        "relaxed_threshold": relaxed_threshold,
        "total_rows": len(rows),
        "evaluated_rows": len(evaluated),
        "skipped_gt_not_sure_rows": len(skipped),
        "exact_match_rows": exact_matches,
        "exact_mismatch_rows": len(evaluated) - exact_matches,
        "relaxed_match_rows": relaxed_matches,
        "relaxed_mismatch_rows": len(evaluated) - relaxed_matches,
        "total_exact_tp": total_exact_tp,
        "total_exact_fp": total_exact_fp,
        "total_exact_fn": total_exact_fn,
        "exact_precision": safe_div(total_exact_tp, total_exact_tp + total_exact_fp),
        "exact_recall": safe_div(total_exact_tp, total_exact_tp + total_exact_fn),
        "exact_f1": safe_div(
            2 * total_exact_tp,
            2 * total_exact_tp + total_exact_fp + total_exact_fn,
        ),
        "total_relaxed_tp": total_relaxed_tp,
        "total_relaxed_fp": total_relaxed_fp,
        "total_relaxed_fn": total_relaxed_fn,
        "relaxed_precision": safe_div(
            total_relaxed_tp,
            total_relaxed_tp + total_relaxed_fp,
        ),
        "relaxed_recall": safe_div(total_relaxed_tp, total_relaxed_tp + total_relaxed_fn),
        "relaxed_f1": safe_div(
            2 * total_relaxed_tp,
            2 * total_relaxed_tp + total_relaxed_fp + total_relaxed_fn,
        ),
    }


def fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def write_report(
    source: str,
    input_csv: Path,
    output_csv: Path,
    output_summary: Path,
    output_report: Path,
    rows: Sequence[Dict[str, Any]],
    summary: Dict[str, Any],
) -> None:
    skipped_ids = [row["sample_id"] for row in rows if row["skipped"]]
    evaluated = [row for row in rows if not row["skipped"]]
    sample_types = sorted({row.get("sample_type", "") for row in rows})

    lines = [
        f"# {source} log-message eval report",
        "",
        "Generated from:",
        "",
        "```bash",
        (
            "python3 rq2.1/eval/scripts/basic_eval_log_msg.py "
            f"--source {source} --out-dir {output_csv.parent}"
        ),
        "```",
        "",
        "Input:",
        f"- `{input_csv}`",
        "",
        "Outputs:",
        f"- `{output_csv}`",
        f"- `{output_summary}`",
        "",
        "## eval setup",
        "",
        "- Evaluation level: log message level.",
        "- GT source: `<log>...</log>` spans from joined `gt_*` annotation columns.",
        "- `gt_not_sure == 1` samples are skipped.",
        "- Log blocks and message lists are deduplicated within each side before comparison.",
        "- Non-timestamp boundary repair is enabled for log-like starts.",
        "- Exact comparison uses text-only normalization.",
        (
            "- Relaxed comparison uses one-to-one token-F1 matching with "
            f"threshold `{summary['relaxed_threshold']}`."
        ),
        "",
        "## skipped samples",
        "",
    ]
    if skipped_ids:
        lines.append("Skipped because `gt_not_sure == 1`:")
        lines.extend(f"- `{sample_id}`" for sample_id in skipped_ids)
    else:
        lines.append("No samples were skipped.")

    lines.extend(
        [
            "",
            "## summary",
            "",
            "| metric | exact | relaxed |",
            "|---|---:|---:|",
            (
                f"| matched rows | {summary['exact_match_rows']} | "
                f"{summary['relaxed_match_rows']} |"
            ),
            (
                f"| mismatch rows | {summary['exact_mismatch_rows']} | "
                f"{summary['relaxed_mismatch_rows']} |"
            ),
            f"| total TP | {summary['total_exact_tp']} | {summary['total_relaxed_tp']} |",
            f"| total FP | {summary['total_exact_fp']} | {summary['total_relaxed_fp']} |",
            f"| total FN | {summary['total_exact_fn']} | {summary['total_relaxed_fn']} |",
            f"| precision | {fmt(summary['exact_precision'])} | {fmt(summary['relaxed_precision'])} |",
            f"| recall | {fmt(summary['exact_recall'])} | {fmt(summary['relaxed_recall'])} |",
            f"| F1 | {fmt(summary['exact_f1'])} | {fmt(summary['relaxed_f1'])} |",
            "",
            "Other counts:",
            f"- total rows: {summary['total_rows']}",
            f"- evaluated rows: {summary['evaluated_rows']}",
            f"- skipped rows: {summary['skipped_gt_not_sure_rows']}",
            "",
            "## row-level match counts",
            "",
            (
                "| sample type | skipped | exact-match rows | relaxed-match rows | "
                "exact mismatch rows | relaxed mismatch rows |"
            ),
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for sample_type in sample_types:
        type_rows = [row for row in rows if row.get("sample_type", "") == sample_type]
        type_evaluated = [row for row in type_rows if not row["skipped"]]
        type_skipped = len(type_rows) - len(type_evaluated)
        exact_matches = sum(1 for row in type_evaluated if row["sample_exact_match"])
        relaxed_matches = sum(1 for row in type_evaluated if row["sample_relaxed_match"])
        lines.append(
            "| {sample_type} | {skipped} | {exact_matches} | {relaxed_matches} | "
            "{exact_mismatches} | {relaxed_mismatches} |".format(
                sample_type=sample_type or "unknown",
                skipped=type_skipped,
                exact_matches=exact_matches,
                relaxed_matches=relaxed_matches,
                exact_mismatches=len(type_evaluated) - exact_matches,
                relaxed_mismatches=len(type_evaluated) - relaxed_matches,
            )
        )

    relaxed_fix_count = sum(
        1
        for row in evaluated
        if not row["sample_exact_match"] and row["sample_relaxed_match"]
    )
    lines.extend(
        [
            "",
            "## notes",
            "",
            (
                f"- Relaxed matching fixes {relaxed_fix_count} evaluated samples "
                "that fail exact matching."
            ),
            "- Detailed per-sample messages and mismatch lists are in the CSV output.",
            "",
        ]
    )
    output_report.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    config = SOURCE_CONFIG[args.source]
    input_csv = args.data_dir / config["input"]
    output_csv = args.out_dir / f"{args.source}_log_msg_eval.csv"
    output_summary = args.out_dir / f"{args.source}_log_msg_eval_summary.json"
    output_report = args.out_dir / f"{args.source}_log_msg_eval_report.md"

    args.out_dir.mkdir(parents=True, exist_ok=True)

    with input_csv.open(newline="", encoding="utf-8-sig") as f:
        input_rows = list(csv.DictReader(f))

    result_rows: List[Dict[str, Any]] = []
    for row in input_rows:
        if is_gt_not_sure(row.get("gt_not_sure", "")):
            result_rows.append(skipped_row(row))
        else:
            result_rows.append(evaluate_row(row, config, args.relaxed_threshold))

    write_results(result_rows, output_csv)
    summary = summarize(args.source, input_csv, result_rows, args.relaxed_threshold)
    output_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_report(
        args.source,
        input_csv,
        output_csv,
        output_summary,
        output_report,
        result_rows,
        summary,
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Wrote {output_csv}")
    print(f"Wrote {output_summary}")
    print(f"Wrote {output_report}")


if __name__ == "__main__":
    main()
