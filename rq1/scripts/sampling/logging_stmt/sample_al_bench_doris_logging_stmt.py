#!/usr/bin/env python3

import argparse
import csv
import re
from collections import Counter
from pathlib import Path


LEVEL_ORDER = ["warn", "info", "debug", "error", "trace", "fatal"]
LENGTH_ORDER = ["q1", "q2", "q3", "q4"]
STYLE_ORDER = ["placeholder", "concat", "string_format", "other"]
VAR_ORDER = ["0", "1", "2", "3", "4+"]

LEVEL_TARGETS = {
    "warn": 9,
    "info": 8,
    "debug": 8,
    "error": 3,
    "trace": 1,
    "fatal": 1,
}

LENGTH_TARGETS = {
    "q1": 8,
    "q2": 7,
    "q3": 7,
    "q4": 8,
}

STYLE_TARGETS = {
    "placeholder": 21,
    "concat": 5,
    "string_format": 2,
    "other": 2,
}

VAR_TARGETS = {
    "0": 3,
    "1": 11,
    "2": 8,
    "3": 4,
    "4+": 4,
}

OUTPUT_FIELDS = [
    "SampleId",
    "SourceLine",
    "Level",
    "MessageLengthBucket",
    "MessageConstructionStyle",
    "VariableCountBucket",
    "LogStatement",
    "Message",
    "VarList",
]


def message_length_bucket(message: str) -> str:
    length = len((message or "").strip())
    if length <= 41:
        return "q1"
    if length <= 61:
        return "q2"
    if length <= 89:
        return "q3"
    return "q4"


def variable_count_bucket(var_list: str) -> str:
    value = (var_list or "").strip()
    if not value:
        return "0"
    count = len([item for item in value.split(",") if item.strip()])
    if count == 0:
        return "0"
    if count == 1:
        return "1"
    if count == 2:
        return "2"
    if count == 3:
        return "3"
    return "4+"


def message_style(log_statement: str) -> str:
    stmt = log_statement or ""
    if "{}" in stmt:
        return "placeholder"
    if "String . format" in stmt or "String.format" in stmt:
        return "string_format"
    if "+" in stmt:
        return "concat"
    return "other"


def normalize_message_key(message: str) -> str:
    text = (message or "").lower()
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\d+", "<num>", text)
    return text


def detokenize_java_like_text(text: str) -> str:
    value = (text or "").strip()
    if not value:
        return value

    substitutions = [
        (r"\s+\.\s+", "."),
        (r"\s+\(\s+", "("),
        (r"\s+\)", ")"),
        (r"\(\s+", "("),
        (r"\s+\[", "["),
        (r"\[\s+", "["),
        (r"\s+\]", "]"),
        (r"\s+;", ";"),
        (r"\s+,", ","),
        (r",(?=\S)", ", "),
        (r"\s+:", ":"),
        (r"\s+\{", " {"),
        (r"\{\s+", "{"),
        (r"\s+\}", "}"),
        (r"\s+<\s+", "<"),
        (r"\s+>\s+", ">"),
    ]

    for pattern, replacement in substitutions:
        value = re.sub(pattern, replacement, value)

    value = re.sub(r"\s+", " ", value).strip()
    return value


def load_rows(src_csv: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with src_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for source_line, row in enumerate(reader, start=2):
            item = dict(row)
            item["SourceLine"] = str(source_line)
            item["MessageLengthBucket"] = message_length_bucket(row.get("Message", ""))
            item["MessageConstructionStyle"] = message_style(row.get("LogStatement", ""))
            item["VariableCountBucket"] = variable_count_bucket(row.get("VarList", ""))
            item["_message_key"] = normalize_message_key(row.get("Message", ""))
            item["_combo_key"] = (
                item.get("Level", ""),
                item["MessageLengthBucket"],
                item["MessageConstructionStyle"],
                item["VariableCountBucket"],
            )
            rows.append(item)
    return rows


def build_availability(rows: list[dict[str, str]]) -> dict[str, Counter]:
    availability = {
        "level": Counter(),
        "length": Counter(),
        "style": Counter(),
        "var": Counter(),
    }
    for row in rows:
        availability["level"][row["Level"]] += 1
        availability["length"][row["MessageLengthBucket"]] += 1
        availability["style"][row["MessageConstructionStyle"]] += 1
        availability["var"][row["VariableCountBucket"]] += 1
    return availability


def build_suffix_level_counts(rows: list[dict[str, str]]) -> list[Counter]:
    suffix_level_counts: list[Counter] = [Counter() for _ in range(len(rows) + 1)]
    running = Counter()
    for index in range(len(rows) - 1, -1, -1):
        running = running.copy()
        running[rows[index]["Level"]] += 1
        suffix_level_counts[index] = running
    return suffix_level_counts


def can_still_meet_level_targets(
    index: int,
    level_counts: Counter,
    suffix_level_counts: list[Counter],
) -> bool:
    remaining_by_level = suffix_level_counts[index + 1]
    for level, target in LEVEL_TARGETS.items():
        if level_counts[level] > target:
            return False
        if level_counts[level] + remaining_by_level[level] < target:
            return False
    return True


def row_score(
    row: dict[str, str],
    availability: dict[str, Counter],
    level_counts: Counter,
    length_counts: Counter,
    style_counts: Counter,
    var_counts: Counter,
    seen_message_keys: set[str],
    seen_combo_keys: set[tuple[str, str, str, str]],
) -> float:
    score = 0.0
    level = row["Level"]
    if level_counts[level] >= LEVEL_TARGETS[level]:
        return float("-inf")

    score += (LEVEL_TARGETS[level] - level_counts[level]) * 1000.0

    length_bucket = row["MessageLengthBucket"]
    if length_counts[length_bucket] < LENGTH_TARGETS[length_bucket]:
        score += 200.0
        score += 300.0 / availability["length"][length_bucket]

    style_bucket = row["MessageConstructionStyle"]
    if style_counts[style_bucket] < STYLE_TARGETS[style_bucket]:
        score += 220.0
        score += 500.0 / availability["style"][style_bucket]

    var_bucket = row["VariableCountBucket"]
    if var_counts[var_bucket] < VAR_TARGETS[var_bucket]:
        score += 180.0
        score += 320.0 / availability["var"][var_bucket]

    if row["_combo_key"] not in seen_combo_keys:
        score += 50.0
    if row["_message_key"] not in seen_message_keys:
        score += 40.0
    else:
        score -= 120.0

    score += 50.0 / availability["level"][level]

    return score


def select_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    availability = build_availability(rows)
    suffix_level_counts = build_suffix_level_counts(rows)

    selected_indices: list[int] = []
    selected_set: set[int] = set()
    level_counts: Counter = Counter()
    length_counts: Counter = Counter()
    style_counts: Counter = Counter()
    var_counts: Counter = Counter()
    seen_message_keys: set[str] = set()
    seen_combo_keys: set[tuple[str, str, str, str]] = set()

    while len(selected_indices) < sum(LEVEL_TARGETS.values()):
        best_index = None
        best_score = float("-inf")

        for index, row in enumerate(rows):
            if index in selected_set:
                continue
            score = row_score(
                row,
                availability,
                level_counts,
                length_counts,
                style_counts,
                var_counts,
                seen_message_keys,
                seen_combo_keys,
            )
            if score == float("-inf"):
                continue

            trial_level_counts = level_counts.copy()
            trial_level_counts[row["Level"]] += 1
            if not can_still_meet_level_targets(index, trial_level_counts, suffix_level_counts):
                continue

            if score > best_score or (
                score == best_score
                and best_index is not None
                and int(rows[index]["SourceLine"]) < int(rows[best_index]["SourceLine"])
            ):
                best_index = index
                best_score = score

        if best_index is None:
            raise RuntimeError("Could not complete deterministic sampling under the configured quotas.")

        chosen = rows[best_index]
        selected_indices.append(best_index)
        selected_set.add(best_index)
        level_counts[chosen["Level"]] += 1
        length_counts[chosen["MessageLengthBucket"]] += 1
        style_counts[chosen["MessageConstructionStyle"]] += 1
        var_counts[chosen["VariableCountBucket"]] += 1
        seen_message_keys.add(chosen["_message_key"])
        seen_combo_keys.add(chosen["_combo_key"])

    selected_rows = [rows[index] for index in selected_indices]
    selected_rows.sort(key=lambda row: int(row["SourceLine"]))
    return selected_rows


def write_output(selected_rows: list[dict[str, str]], dst_csv: Path) -> None:
    dst_csv.parent.mkdir(parents=True, exist_ok=True)
    output_rows = []
    for sample_id, row in enumerate(selected_rows, start=1):
        output_rows.append(
            {
                "SampleId": sample_id,
                "SourceLine": row["SourceLine"],
                "Level": row["Level"],
                "MessageLengthBucket": row["MessageLengthBucket"],
                "MessageConstructionStyle": row["MessageConstructionStyle"],
                "VariableCountBucket": row["VariableCountBucket"],
                "LogStatement": detokenize_java_like_text(row.get("LogStatement", "")),
                "Message": row.get("Message", ""),
                "VarList": row.get("VarList", ""),
            }
        )

    with dst_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(output_rows)


def print_summary(selected_rows: list[dict[str, str]]) -> None:
    print(f"selected_rows={len(selected_rows)}")
    print("level_counts", dict(Counter(row["Level"] for row in selected_rows)))
    print("message_length_counts", dict(Counter(row["MessageLengthBucket"] for row in selected_rows)))
    print("style_counts", dict(Counter(row["MessageConstructionStyle"] for row in selected_rows)))
    print("variable_count_counts", dict(Counter(row["VariableCountBucket"] for row in selected_rows)))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deterministically sample 30 AL_Bench Doris logging statements for RQ1."
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=Path("RQ1/dataset/backup/privious_resources/logging_stmt/AL_Bench/doris_log_ground_truth.csv"),
        help="Path to the AL_Bench Doris ground-truth CSV.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("RQ1/dataset/logging_stmt/AL_Bench_doris_log.csv"),
        help="Path for the sampled output CSV.",
    )
    args = parser.parse_args()

    rows = load_rows(args.input_csv)
    selected_rows = select_rows(rows)
    write_output(selected_rows, args.output_csv)
    print_summary(selected_rows)


if __name__ == "__main__":
    main()
