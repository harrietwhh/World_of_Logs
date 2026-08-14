#!/usr/bin/env python3
"""Run uncertainty-thresholded RQ2.1 log-message evaluation."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
BASIC_EVAL_PATH = SCRIPT_DIR / "basic_eval_log_msg.py"
DEFAULT_THRESHOLDS = (0.01, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50)
SOURCES = ("github", "jira", "so", "cc")


def load_basic_eval_module() -> Any:
    spec = importlib.util.spec_from_file_location("basic_eval_log_msg", BASIC_EVAL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {BASIC_EVAL_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


basic = load_basic_eval_module()


@dataclass
class BlockFilterStats:
    kept_blocks: int = 0
    discarded_uncertainty_blocks: int = 0
    discarded_missing_uncertainty_blocks: int = 0
    kept_messages: int = 0
    discarded_uncertainty_messages: int = 0
    discarded_missing_uncertainty_messages: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate log-message extraction after pred_uncertainty filtering."
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=SOURCES,
        default=list(SOURCES),
        help="Sources to evaluate. Defaults to all sources.",
    )
    parser.add_argument(
        "--thresholds",
        nargs="+",
        type=float,
        default=list(DEFAULT_THRESHOLDS),
        help="Uncertainty thresholds to evaluate.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("rq2.1/eval/data"),
        help="Directory containing joined audit sample CSVs.",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("rq2.1/eval/results"),
        help="Directory for eval results.",
    )
    parser.add_argument(
        "--basic-results-dir",
        type=Path,
        default=Path("rq2.1/eval/results/basic_eval"),
        help="Directory containing no-threshold basic eval summaries.",
    )
    parser.add_argument(
        "--relaxed-threshold",
        type=float,
        default=basic.DEFAULT_RELAXED_THRESHOLD,
        help="Minimum token-level F1 for relaxed one-to-one message matching.",
    )
    return parser.parse_args()


def threshold_label(threshold: float) -> str:
    return f"{threshold:.2f}"


def threshold_dir_name(threshold: float) -> str:
    return f"uncertainty_le_{threshold_label(threshold)}"


def parse_uncertainty(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed):
        return None
    return parsed


def split_messages_for_stats(blocks: Sequence[str], config: Dict[str, Any]) -> int:
    split_non_timestamp_lines = bool(config.get("split_non_timestamp_log_lines"))
    messages = basic.strip_empty(
        basic.extract_log_messages_from_block(
            basic.join_blocks(blocks),
            split_non_timestamp_lines,
        )
    )
    unique_messages, _ = basic.dedupe_by_normalized(messages)
    return len(unique_messages)


def add_blocks_by_threshold(
    value: Any,
    uncertainty: Any,
    threshold: float,
    kept_blocks: List[str],
    discarded_uncertainty_blocks: List[str],
    discarded_missing_uncertainty_blocks: List[str],
) -> None:
    blocks = basic.split_blocks(value)
    if not blocks:
        return

    parsed_uncertainty = parse_uncertainty(uncertainty)
    if parsed_uncertainty is None:
        discarded_missing_uncertainty_blocks.extend(blocks)
    elif parsed_uncertainty <= threshold:
        kept_blocks.extend(blocks)
    else:
        discarded_uncertainty_blocks.extend(blocks)


def dedupe_block_candidates_by_normalized(
    candidates: Sequence[Tuple[str, Any]],
) -> List[Tuple[str, Any]]:
    normalized_to_candidate: Dict[str, Tuple[str, Any]] = {}
    for block, uncertainty in candidates:
        key = basic.text_only_normalize(block)
        if not key:
            continue
        parsed_uncertainty = parse_uncertainty(uncertainty)
        if key not in normalized_to_candidate:
            normalized_to_candidate[key] = (block, uncertainty)
            continue
        _existing_block, existing_uncertainty = normalized_to_candidate[key]
        existing_parsed = parse_uncertainty(existing_uncertainty)
        if existing_parsed is None or (
            parsed_uncertainty is not None and parsed_uncertainty < existing_parsed
        ):
            normalized_to_candidate[key] = (block, uncertainty)
    return list(normalized_to_candidate.values())


def extract_thresholded_inference_blocks(
    row: Dict[str, str],
    config: Dict[str, Any],
    threshold: float,
) -> Tuple[List[str], BlockFilterStats]:
    candidates: List[Tuple[str, Any]] = []
    kept_blocks: List[str] = []
    discarded_uncertainty_blocks: List[str] = []
    discarded_missing_uncertainty_blocks: List[str] = []

    for col in config["inference_text_cols"]:
        for block in basic.split_blocks(row.get(col, "")):
            candidates.append((block, row.get("pred_uncertainty", "")))

    for col in config["inference_json_cols"]:
        for item in basic.parse_jsonish_list(row.get(col, "")):
            if isinstance(item, dict):
                value = item.get("log_blks", "")
                uncertainty = item.get("pred_uncertainty")
            else:
                value = item
                uncertainty = None
            for block in basic.split_blocks(value):
                candidates.append((block, uncertainty))

    for block, uncertainty in dedupe_block_candidates_by_normalized(candidates):
        add_blocks_by_threshold(
            block,
            uncertainty,
            threshold,
            kept_blocks,
            discarded_uncertainty_blocks,
            discarded_missing_uncertainty_blocks,
        )

    stats = BlockFilterStats(
        kept_blocks=len(kept_blocks),
        discarded_uncertainty_blocks=len(discarded_uncertainty_blocks),
        discarded_missing_uncertainty_blocks=len(discarded_missing_uncertainty_blocks),
        kept_messages=split_messages_for_stats(kept_blocks, config),
        discarded_uncertainty_messages=split_messages_for_stats(
            discarded_uncertainty_blocks,
            config,
        ),
        discarded_missing_uncertainty_messages=split_messages_for_stats(
            discarded_missing_uncertainty_blocks,
            config,
        ),
    )
    return kept_blocks, stats


def evaluate_thresholded_row(
    row: Dict[str, str],
    config: Dict[str, Any],
    threshold: float,
    relaxed_threshold: float,
) -> Dict[str, Any]:
    inference_blocks, filter_stats = extract_thresholded_inference_blocks(
        row,
        config,
        threshold,
    )
    gt_blocks = basic.extract_gt_blocks(row, config)
    inference_blks = basic.join_blocks(inference_blocks)
    gt_blks = basic.join_blocks(gt_blocks)

    split_non_timestamp_lines = bool(config.get("split_non_timestamp_log_lines"))
    inference_msgs = basic.strip_empty(
        basic.extract_log_messages_from_block(inference_blks, split_non_timestamp_lines)
    )
    gt_msgs = basic.strip_empty(
        basic.extract_log_messages_from_block(gt_blks, split_non_timestamp_lines)
    )

    unique_inference_msgs, inference_norm_map = basic.dedupe_by_normalized(inference_msgs)
    unique_gt_msgs, gt_norm_map = basic.dedupe_by_normalized(gt_msgs)

    inference_norms = set(inference_norm_map)
    gt_norms = set(gt_norm_map)
    matched_norms = inference_norms & gt_norms
    inference_only_norms = sorted(inference_norms - gt_norms)
    gt_only_norms = sorted(gt_norms - inference_norms)
    relaxed_pairs, relaxed_inference_only_indices, relaxed_gt_only_indices = (
        basic.relaxed_one_to_one_match(unique_inference_msgs, unique_gt_msgs, relaxed_threshold)
    )

    return {
        "sample_id": row.get("sample_id", ""),
        "source": row.get("source", ""),
        "sample_type": row.get("sample_type", ""),
        "url": row.get("url", ""),
        "gt_not_sure": row.get("gt_not_sure", ""),
        "skipped": False,
        "uncertainty_threshold": threshold_label(threshold),
        "kept_inference_block_count": filter_stats.kept_blocks,
        "discarded_uncertainty_block_count": filter_stats.discarded_uncertainty_blocks,
        "discarded_missing_uncertainty_block_count": (
            filter_stats.discarded_missing_uncertainty_blocks
        ),
        "kept_inference_msg_count_before_dedupe": filter_stats.kept_messages,
        "discarded_uncertainty_msg_count": filter_stats.discarded_uncertainty_messages,
        "discarded_missing_uncertainty_msg_count": (
            filter_stats.discarded_missing_uncertainty_messages
        ),
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
        "sample_relaxed_match": not relaxed_inference_only_indices
        and not relaxed_gt_only_indices,
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


def skipped_thresholded_row(row: Dict[str, str], threshold: float) -> Dict[str, Any]:
    skipped = basic.skipped_row(row)
    skipped.update(
        {
            "uncertainty_threshold": threshold_label(threshold),
            "kept_inference_block_count": 0,
            "discarded_uncertainty_block_count": 0,
            "discarded_missing_uncertainty_block_count": 0,
            "kept_inference_msg_count_before_dedupe": 0,
            "discarded_uncertainty_msg_count": 0,
            "discarded_missing_uncertainty_msg_count": 0,
        }
    )
    return skipped


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
        "uncertainty_threshold",
        "kept_inference_block_count",
        "discarded_uncertainty_block_count",
        "discarded_missing_uncertainty_block_count",
        "kept_inference_msg_count_before_dedupe",
        "discarded_uncertainty_msg_count",
        "discarded_missing_uncertainty_msg_count",
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
    threshold: float,
    relaxed_threshold: float,
) -> Dict[str, Any]:
    summary = basic.summarize(source, input_csv, rows, relaxed_threshold)
    evaluated = [row for row in rows if not row["skipped"]]
    summary.update(
        {
            "uncertainty_threshold": threshold_label(threshold),
            "kept_inference_blocks": sum(
                int(row["kept_inference_block_count"]) for row in evaluated
            ),
            "discarded_uncertainty_blocks": sum(
                int(row["discarded_uncertainty_block_count"]) for row in evaluated
            ),
            "discarded_missing_uncertainty_blocks": sum(
                int(row["discarded_missing_uncertainty_block_count"]) for row in evaluated
            ),
            "kept_inference_messages_before_dedupe": sum(
                int(row["kept_inference_msg_count_before_dedupe"]) for row in evaluated
            ),
            "discarded_uncertainty_messages": sum(
                int(row["discarded_uncertainty_msg_count"]) for row in evaluated
            ),
            "discarded_missing_uncertainty_messages": sum(
                int(row["discarded_missing_uncertainty_msg_count"]) for row in evaluated
            ),
        }
    )
    return summary


def run_source_threshold(
    source: str,
    threshold: float,
    data_dir: Path,
    output_dir: Path,
    relaxed_threshold: float,
) -> Dict[str, Any]:
    config = basic.SOURCE_CONFIG[source]
    input_csv = data_dir / config["input"]

    with input_csv.open(newline="", encoding="utf-8-sig") as f:
        input_rows = list(csv.DictReader(f))

    result_rows: List[Dict[str, Any]] = []
    for row in input_rows:
        if basic.is_gt_not_sure(row.get("gt_not_sure", "")):
            result_rows.append(skipped_thresholded_row(row, threshold))
        else:
            result_rows.append(
                evaluate_thresholded_row(row, config, threshold, relaxed_threshold)
            )

    output_csv = output_dir / f"{source}_log_msg_eval.csv"
    output_summary = output_dir / f"{source}_log_msg_eval_summary.json"
    write_results(result_rows, output_csv)
    summary = summarize(source, input_csv, result_rows, threshold, relaxed_threshold)
    output_summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def load_basic_summary(source: str, basic_results_dir: Path) -> Dict[str, Any]:
    summary_path = basic_results_dir / f"{source}_log_msg_eval_summary.json"
    return json.loads(summary_path.read_text(encoding="utf-8"))


def write_threshold_report(
    threshold: float,
    output_dir: Path,
    summaries: Sequence[Dict[str, Any]],
    basic_results_dir: Path,
) -> None:
    lines = [
        f"# Uncertainty <= {threshold_label(threshold)} eval report",
        "",
        "Generated from:",
        "",
        "```bash",
        (
            "python3 rq2.1/eval/scripts/uncertainty_eval_log_msg.py "
            f"--thresholds {threshold_label(threshold)}"
        ),
        "```",
        "",
        "Inference blocks are kept only when `pred_uncertainty` is numeric and",
        f"`<= {threshold_label(threshold)}`. GT is not filtered.",
        "",
        "Eval setup:",
        "- Exact match uses the same text-only normalization as basic eval, ignoring",
        "  whitespace, newlines, and separator punctuation.",
        "- Relaxed match uses the same one-to-one token-F1 >= 0.8 rule as basic eval.",
        "- GT extraction, `gt_not_sure` filtering, log-message splitting, boundary",
        "  repair, and block/message deduplication are unchanged from basic eval.",
        "",
        "## summary",
        "",
        (
            "| source | evaluated | kept blocks | discarded > threshold | "
            "discarded missing | exact F1 | relaxed F1 | relaxed P | relaxed R |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for summary in summaries:
        lines.append(
            "| {source} | {evaluated_rows} | {kept_inference_blocks} | "
            "{discarded_uncertainty_blocks} | {discarded_missing_uncertainty_blocks} | "
            "{exact_f1} | {relaxed_f1} | {relaxed_precision} | {relaxed_recall} |".format(
                source=summary["source"],
                evaluated_rows=summary["evaluated_rows"],
                kept_inference_blocks=summary["kept_inference_blocks"],
                discarded_uncertainty_blocks=summary["discarded_uncertainty_blocks"],
                discarded_missing_uncertainty_blocks=(
                    summary["discarded_missing_uncertainty_blocks"]
                ),
                exact_f1=fmt(summary["exact_f1"]),
                relaxed_f1=fmt(summary["relaxed_f1"]),
                relaxed_precision=fmt(summary["relaxed_precision"]),
                relaxed_recall=fmt(summary["relaxed_recall"]),
            )
        )
    lines.extend(
        [
            "",
            "## basic-setting comparison",
            "",
            "| source | basic-setting relaxed F1 | threshold relaxed F1 | delta |",
            "|---|---:|---:|---:|",
        ]
    )
    for summary in summaries:
        basic_setting = load_basic_summary(summary["source"], basic_results_dir)
        delta = summary["relaxed_f1"] - basic_setting["relaxed_f1"]
        lines.append(
            f"| {summary['source']} | {basic_setting['relaxed_f1']:.4f} | "
            f"{summary['relaxed_f1']:.4f} | {delta:+.4f} |"
        )
    lines.append("")
    output_dir.joinpath("threshold_report.md").write_text("\n".join(lines), encoding="utf-8")


def write_comparison_report(
    all_summaries: Dict[float, List[Dict[str, Any]]],
    results_dir: Path,
    basic_results_dir: Path,
) -> None:
    lines = [
        "# Uncertainty-threshold comparison report",
        "",
        "Basic setting (no filtering): `rq2.1/eval/results/basic_eval/`.",
        "",
        "Thresholded outputs are stored under `uncertainty_le_<t>/` folders.",
        "",
        "## eval setup",
        "",
        "- The threshold only filters inference-side log blocks. GT is not filtered.",
        "- Exact match is the same text-only exact match used in basic eval: normalize",
        "  text and ignore non-text differences such as whitespace, newlines, and",
        "  separator punctuation.",
        "- Relaxed match is also the same as basic eval: one-to-one message matching",
        "  with token-level F1 >= 0.8.",
        "- GT extraction, `gt_not_sure` sample filtering, log-message splitting,",
        "  boundary repair, and block/message deduplication are unchanged from basic eval.",
        "",
        "## text-only exact F1 by source",
        "",
        "Exact match here is the semantic text-only exact match from basic eval, not raw",
        "string equality.",
        "",
        "| source | basic setting | "
        + " | ".join(f"<={threshold_label(threshold)}" for threshold in DEFAULT_THRESHOLDS)
        + " |",
        "|---|---:|" + "---:|" * len(DEFAULT_THRESHOLDS),
    ]
    for source in SOURCES:
        basic_setting = load_basic_summary(source, basic_results_dir)
        values = []
        for threshold in DEFAULT_THRESHOLDS:
            summaries = {summary["source"]: summary for summary in all_summaries[threshold]}
            values.append(summaries[source]["exact_f1"])
        lines.append(
            f"| {source} | {basic_setting['exact_f1']:.4f} | "
            + " | ".join(f"{value:.4f}" for value in values)
            + " |"
        )

    lines.extend(
        [
            "",
        "## relaxed F1 by source",
        "",
        "| source | basic setting | "
        + " | ".join(f"<={threshold_label(threshold)}" for threshold in DEFAULT_THRESHOLDS)
        + " |",
        "|---|---:|" + "---:|" * len(DEFAULT_THRESHOLDS),
        ]
    )
    for source in SOURCES:
        basic_setting = load_basic_summary(source, basic_results_dir)
        values = []
        for threshold in DEFAULT_THRESHOLDS:
            summaries = {summary["source"]: summary for summary in all_summaries[threshold]}
            values.append(summaries[source]["relaxed_f1"])
        lines.append(
            f"| {source} | {basic_setting['relaxed_f1']:.4f} | "
            + " | ".join(f"{value:.4f}" for value in values)
            + " |"
        )

    lines.extend(
        [
            "",
            "## exact precision / recall by threshold",
            "",
            (
                "| threshold | source | kept blocks | discarded > threshold | "
                "discarded missing | exact P | exact R | exact F1 |"
            ),
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for threshold in DEFAULT_THRESHOLDS:
        for summary in all_summaries[threshold]:
            lines.append(
                "| <= {threshold} | {source} | {kept} | {discarded} | {missing} | "
                "{precision} | {recall} | {f1} |".format(
                    threshold=threshold_label(threshold),
                    source=summary["source"],
                    kept=summary["kept_inference_blocks"],
                    discarded=summary["discarded_uncertainty_blocks"],
                    missing=summary["discarded_missing_uncertainty_blocks"],
                    precision=fmt(summary["exact_precision"]),
                    recall=fmt(summary["exact_recall"]),
                    f1=fmt(summary["exact_f1"]),
                )
            )

    lines.extend(
        [
            "",
            "## relaxed precision / recall by threshold",
            "",
            (
                "| threshold | source | kept blocks | discarded > threshold | "
                "discarded missing | relaxed P | relaxed R | relaxed F1 |"
            ),
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for threshold in DEFAULT_THRESHOLDS:
        for summary in all_summaries[threshold]:
            lines.append(
                "| <= {threshold} | {source} | {kept} | {discarded} | {missing} | "
                "{precision} | {recall} | {f1} |".format(
                    threshold=threshold_label(threshold),
                    source=summary["source"],
                    kept=summary["kept_inference_blocks"],
                    discarded=summary["discarded_uncertainty_blocks"],
                    missing=summary["discarded_missing_uncertainty_blocks"],
                    precision=fmt(summary["relaxed_precision"]),
                    recall=fmt(summary["relaxed_recall"]),
                    f1=fmt(summary["relaxed_f1"]),
                )
            )
    lines.extend(
        [
            "",
            "## notes",
            "",
            "- Lower thresholds keep fewer inference blocks, so precision may increase while recall drops.",
            "- Blocks with missing or `NaN` uncertainty are excluded in thresholded runs.",
            "- GT extraction and `gt_not_sure` filtering are unchanged from basic eval.",
            "",
        ]
    )
    results_dir.joinpath("uncertainty_threshold_comparison_report.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    args.results_dir.mkdir(parents=True, exist_ok=True)

    all_summaries: Dict[float, List[Dict[str, Any]]] = {}
    for threshold in args.thresholds:
        output_dir = args.results_dir / threshold_dir_name(threshold)
        output_dir.mkdir(parents=True, exist_ok=True)
        threshold_summaries: List[Dict[str, Any]] = []
        for source in args.sources:
            threshold_summaries.append(
                run_source_threshold(
                    source,
                    threshold,
                    args.data_dir,
                    output_dir,
                    args.relaxed_threshold,
                )
            )
        all_summaries[threshold] = threshold_summaries
        write_threshold_report(
            threshold,
            output_dir,
            threshold_summaries,
            args.basic_results_dir,
        )

    if set(args.sources) == set(SOURCES) and tuple(args.thresholds) == DEFAULT_THRESHOLDS:
        write_comparison_report(all_summaries, args.results_dir, args.basic_results_dir)

    print(json.dumps(all_summaries, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
