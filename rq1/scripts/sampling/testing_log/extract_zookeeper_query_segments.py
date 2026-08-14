#!/usr/bin/env python3

import argparse
import csv
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


DEFAULT_SELECTED_CSV = Path(
    "RQ1/dataset/testing_log/testing_log_selected_30_query_1_5_lines_zookeeper_only.csv"
)
DEFAULT_LOG_ROOT = Path(
    "RQ1/dataset/backup/privious_resources/testing_log/sample_500_logs"
)
DEFAULT_OUTPUT_CSV = Path(
    "RQ1/dataset/testing_log/zookeeper_query_segments_candidates.csv"
)


@dataclass(frozen=True)
class SignalRule:
    name: str
    weight: int
    pattern: re.Pattern[str]


SIGNAL_RULES = [
    SignalRule(
        "starting_test_method",
        10,
        re.compile(r"STARTING .*test[A-Za-z0-9_]+", re.IGNORECASE),
    ),
    SignalRule(
        "setup_teardown",
        8,
        re.compile(r"\b(setUp|tearDown|setup|teardown)\b", re.IGNORECASE),
    ),
    SignalRule(
        "assigned_port",
        7,
        re.compile(r"Assigned port .* from range|Test process .* using ports", re.IGNORECASE),
    ),
    SignalRule(
        "junit_temp_dir",
        7,
        re.compile(r"surefire/test\d+\.junit\.dir|target/surefire/test\d+", re.IGNORECASE),
    ),
    SignalRule(
        "expected_exception",
        7,
        re.compile(r"Expected exception|Expected failure", re.IGNORECASE),
    ),
    SignalRule(
        "tests_only_comment",
        6,
        re.compile(r"only happen in tests|This should only happen in tests", re.IGNORECASE),
    ),
    SignalRule(
        "test_case_line",
        5,
        re.compile(r"\b(ZKTestCase|JUnit|Surefire)\b", re.IGNORECASE),
    ),
    SignalRule(
        "named_test_logger",
        4,
        re.compile(r"\b[A-Za-z0-9]+Test\b", re.IGNORECASE),
    ),
    SignalRule(
        "auth_failure",
        4,
        re.compile(r"Auth|SASL|authentication|required", re.IGNORECASE),
    ),
    SignalRule(
        "quorum_action",
        3,
        re.compile(r"QuorumPeer|creating QuorumPeer|voting view|leader|follower|observer", re.IGNORECASE),
    ),
]


def load_selected_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize_for_repeat(line: str) -> str:
    lowered = re.sub(r"\d+", "<num>", line.lower())
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


def score_line(line: str) -> tuple[int, set[str]]:
    score = 0
    hits: set[str] = set()
    for rule in SIGNAL_RULES:
        if rule.pattern.search(line):
            score += rule.weight
            hits.add(rule.name)
    return score, hits


def score_window(lines: list[str], start: int, end: int) -> tuple[int, set[str], list[int]]:
    window = lines[start : end + 1]
    total = 0
    hits: set[str] = set()
    line_scores: list[int] = []
    nonempty = [line for line in window if line.strip()]

    for line in window:
        line_score, line_hits = score_line(line)
        total += line_score
        hits.update(line_hits)
        line_scores.append(line_score)

    if len(nonempty) >= 2:
        total += 1

    if "starting_test_method" in hits and ("assigned_port" in hits or "setup_teardown" in hits):
        total += 4
        hits.add("coherent_test_window")

    if "expected_exception" in hits and len(nonempty) >= 2:
        total += 2
        hits.add("exception_context")

    if "junit_temp_dir" in hits and ("assigned_port" in hits or "test_case_line" in hits):
        total += 3
        hits.add("explicit_test_env")

    normalized = [normalize_for_repeat(line) for line in nonempty]
    if len(normalized) >= 2 and len(set(normalized)) == 1:
        total -= 6
        hits.add("repetitive_window_penalty")

    if all(score == 0 for score in line_scores):
        total -= 10
        hits.add("no_signal_penalty")

    return total, hits, line_scores


def candidate_windows(anchor: int, n_lines: int) -> set[tuple[int, int]]:
    windows: set[tuple[int, int]] = set()
    for length in range(1, 6):
        for offset in range(length):
            start = anchor - offset
            end = start + length - 1
            if start < 0 or end >= n_lines:
                continue
            windows.add((start, end))
    return windows


def extract_segments_for_file(rel_path: str, log_root: Path, max_per_file: int) -> list[dict[str, str]]:
    path = log_root / rel_path
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    if not lines:
        return []

    anchors = []
    for i, line in enumerate(lines):
        score, hits = score_line(line)
        if score >= 7 or "starting_test_method" in hits or "expected_exception" in hits:
            anchors.append(i)

    seen = set()
    candidates = []
    for anchor in anchors:
        for start, end in candidate_windows(anchor, len(lines)):
            if (start, end) in seen:
                continue
            seen.add((start, end))
            score, hits, line_scores = score_window(lines, start, end)
            if score < 10:
                continue
            if "repetitive_window_penalty" in hits or "no_signal_penalty" in hits:
                continue
            segment_text = "\n".join(lines[start : end + 1])
            candidates.append(
                {
                    "RelativePath": rel_path,
                    "SegmentStartLine": str(start + 1),
                    "SegmentEndLine": str(end + 1),
                    "SegmentLineCount": str(end - start + 1),
                    "SegmentScore": str(score),
                    "MatchedSignals": ";".join(sorted(hits)),
                    "AnchorStrength": str(max(line_scores)),
                    "SegmentText": segment_text,
                }
            )

    candidates.sort(
        key=lambda row: (
            -int(row["SegmentScore"]),
            int(row["SegmentLineCount"]),
            int(row["SegmentStartLine"]),
        )
    )

    selected = []
    occupied: set[int] = set()
    for row in candidates:
        start = int(row["SegmentStartLine"])
        end = int(row["SegmentEndLine"])
        current = set(range(start, end + 1))
        if occupied & current:
            continue
        selected.append(row)
        occupied.update(current)
        if len(selected) == max_per_file:
            break
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract 1-5 line query segments from selected zookeeper testing logs."
    )
    parser.add_argument("--selected-csv", type=Path, default=DEFAULT_SELECTED_CSV)
    parser.add_argument("--log-root", type=Path, default=DEFAULT_LOG_ROOT)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--max-per-file", type=int, default=3)
    args = parser.parse_args()

    rows = load_selected_rows(args.selected_csv)
    all_segments = []
    for row in rows:
        segments = extract_segments_for_file(row["RelativePath"], args.log_root, args.max_per_file)
        for segment in segments:
            segment["Repo"] = row["Repo"]
            segment["ModulePath"] = row["ModulePath"]
            segment["TestName"] = row["TestName"]
            segment["FileLevel"] = row["FileLevel"]
            segment["FileScore"] = row["FileScore"]
            segment["ExplicitScore"] = row["ExplicitScore"]
        all_segments.extend(segments)

    all_segments.sort(
        key=lambda row: (
            -int(row["SegmentScore"]),
            -int(row["ExplicitScore"]),
            int(row["SegmentLineCount"]),
            row["TestName"],
            int(row["SegmentStartLine"]),
        )
    )

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "Repo",
        "ModulePath",
        "TestName",
        "RelativePath",
        "FileLevel",
        "FileScore",
        "ExplicitScore",
        "SegmentStartLine",
        "SegmentEndLine",
        "SegmentLineCount",
        "SegmentScore",
        "MatchedSignals",
        "AnchorStrength",
        "SegmentText",
    ]
    with args.output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_segments)

    per_file = Counter(row["TestName"] for row in all_segments)
    print(f"Wrote {len(all_segments)} segments to {args.output_csv}")
    print(f"Files with at least one segment: {len(per_file)}")
    print("Top 15 segments:")
    for row in all_segments[:15]:
        print(
            f"{row['SegmentScore']}\t{row['TestName']}\t"
            f"{row['SegmentStartLine']}-{row['SegmentEndLine']}\t{row['MatchedSignals']}"
        )


if __name__ == "__main__":
    main()
