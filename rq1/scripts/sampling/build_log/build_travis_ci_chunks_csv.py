#!/usr/bin/env python3

import argparse
import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET


def build_id_sort_key(build_id: str) -> tuple[int, str]:
    return (int(build_id), build_id) if build_id.isdigit() else (10**18, build_id)


@dataclass(frozen=True)
class ChunkExample:
    language: str
    repo: str
    build_id: str
    log_path: str
    category: str
    keywords: str
    content: str

    @property
    def line_count(self) -> int:
        return len(self.content.splitlines())


def collect_examples(xml_dir: Path, max_lines: int) -> dict[str, dict[str, list[ChunkExample]]]:
    examples_by_language: dict[str, dict[str, list[ChunkExample]]] = defaultdict(lambda: defaultdict(list))

    for xml_path in sorted(xml_dir.rglob("*.xml")):
        language = xml_path.parent.name
        repo = xml_path.stem
        tree = ET.parse(xml_path)

        for example in tree.getroot().findall("Example"):
            content = example.findtext("Chunk") or ""
            if len(content.splitlines()) > max_lines:
                continue

            log_path = (example.findtext("Log") or "").strip()
            build_id = Path(log_path).stem
            examples_by_language[language][repo].append(
                ChunkExample(
                    language=language,
                    repo=repo,
                    build_id=build_id,
                    log_path=log_path,
                    category=(example.findtext("Category") or "").strip(),
                    keywords=(example.findtext("Keywords") or "").strip(),
                    content=content,
                )
            )

    normalized: dict[str, dict[str, list[ChunkExample]]] = {}
    for language, repos in examples_by_language.items():
        normalized[language] = {}
        for repo, items in repos.items():
            normalized[language][repo] = sorted(
                items,
                key=lambda item: (
                    build_id_sort_key(item.build_id),
                    item.line_count,
                    item.content,
                ),
            )

    if not normalized:
        raise ValueError(f"No XML chunks with <= {max_lines} lines found under {xml_dir}")

    return dict(sorted(normalized.items()))


def select_examples(
    examples_by_language: dict[str, dict[str, list[ChunkExample]]], sample_size: int
) -> list[ChunkExample]:
    all_examples = [
        example
        for language in sorted(examples_by_language)
        for repo in sorted(examples_by_language[language])
        for example in examples_by_language[language][repo]
    ]
    if not all_examples:
        raise ValueError("No eligible examples available")

    by_category: dict[str, list[ChunkExample]] = defaultdict(list)
    by_language: dict[str, list[ChunkExample]] = defaultdict(list)
    for example in all_examples:
        by_category[example.category].append(example)
        by_language[example.language].append(example)

    selections: list[ChunkExample] = []
    selected_keys: set[tuple[str, str, str]] = set()
    selected_languages: set[str] = set()
    selected_repos: set[tuple[str, str]] = set()
    selected_category_counts: Counter[str] = Counter()

    def is_selected(example: ChunkExample) -> bool:
        return (example.language, example.repo, example.build_id) in selected_keys

    def add_selection(example: ChunkExample) -> None:
        selections.append(example)
        selected_keys.add((example.language, example.repo, example.build_id))
        selected_languages.add(example.language)
        selected_repos.add((example.language, example.repo))
        selected_category_counts[example.category] += 1

    # Pass 1: cover every available category first, prioritizing new languages and repos.
    for category in sorted(by_category, key=int):
        candidates = [example for example in by_category[category] if not is_selected(example)]
        candidates.sort(
            key=lambda example: (
                0 if example.language not in selected_languages else 1,
                0 if (example.language, example.repo) not in selected_repos else 1,
                build_id_sort_key(example.build_id),
                example.language,
                example.repo,
            )
        )
        add_selection(candidates[0])

    if len(selections) > sample_size:
        raise ValueError(
            f"Category coverage needs {len(selections)} samples, which exceeds sample size {sample_size}"
        )

    # Pass 2: cover every language that still has an eligible 2-5-line chunk.
    for language in sorted(by_language):
        if language in selected_languages:
            continue

        candidates = [example for example in by_language[language] if not is_selected(example)]
        candidates.sort(
            key=lambda example: (
                selected_category_counts[example.category],
                int(example.category),
                0 if (example.language, example.repo) not in selected_repos else 1,
                build_id_sort_key(example.build_id),
                example.repo,
            )
        )
        add_selection(candidates[0])

    # Pass 3: fill remaining slots by always choosing from the currently least represented category.
    while len(selections) < sample_size:
        min_category_count = min(selected_category_counts[category] for category in by_category)
        target_categories = [
            category
            for category in sorted(by_category, key=int)
            if selected_category_counts[category] == min_category_count
        ]

        chosen: ChunkExample | None = None
        for category in target_categories:
            candidates = [example for example in by_category[category] if not is_selected(example)]
            if not candidates:
                continue
            candidates.sort(
                key=lambda example: (
                    0 if (example.language, example.repo) not in selected_repos else 1,
                    build_id_sort_key(example.build_id),
                    example.language,
                    example.repo,
                )
            )
            chosen = candidates[0]
            break

        if chosen is None:
            break
        add_selection(chosen)

    if len(selections) != sample_size:
        raise ValueError(
            f"Only {len(selections)} eligible short-chunk samples found for the current selection rule"
        )

    return selections


def write_csv(selections: list[ChunkExample], output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "LineId",
                "Language",
                "Repo",
                "BuildId",
                "Log",
                "Category",
                "Keywords",
                "Content",
            ],
        )
        writer.writeheader()
        for line_id, item in enumerate(selections, start=1):
            writer.writerow(
                {
                    "LineId": str(line_id),
                    "Language": item.language,
                    "Repo": item.repo,
                    "BuildId": item.build_id,
                    "Log": item.log_path,
                    "Category": item.category,
                    "Keywords": item.keywords,
                    "Content": item.content,
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sample short manually labeled Travis CI chunks directly from XML."
    )
    parser.add_argument(
        "--xml-dir",
        type=Path,
        default=Path(
            "RQ1/dataset/backup/privious_resources/build_log/LogChunks/build-failure-reason"
        ),
        help="Directory containing the original manually labeled XML chunk files.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("RQ1/dataset/build_log/Travis_CI_chunks.csv"),
        help="Output CSV path.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=30,
        help="Number of samples to select.",
    )
    parser.add_argument(
        "--max-lines",
        type=int,
        default=5,
        help="Maximum allowed line count for a sampled XML chunk.",
    )
    parser.add_argument(
        "--min-lines",
        type=int,
        default=2,
        help="Minimum allowed line count for a sampled XML chunk.",
    )
    args = parser.parse_args()

    if args.min_lines > args.max_lines:
        raise ValueError("--min-lines cannot be greater than --max-lines")

    examples_by_language = collect_examples(args.xml_dir, args.max_lines)
    examples_by_language = {
        language: {
            repo: [
                example
                for example in items
                if args.min_lines <= example.line_count <= args.max_lines
            ]
            for repo, items in repos.items()
        }
        for language, repos in examples_by_language.items()
    }
    examples_by_language = {
        language: {repo: items for repo, items in repos.items() if items}
        for language, repos in examples_by_language.items()
    }
    examples_by_language = {language: repos for language, repos in examples_by_language.items() if repos}
    selections = select_examples(examples_by_language, args.sample_size)
    write_csv(selections, args.output_csv)

    print(f"rows={len(selections)}")
    print(f"languages_covered={len({item.language for item in selections})}")
    print(f"repos_covered={len({(item.language, item.repo) for item in selections})}")
    print(f"line_range={args.min_lines}-{args.max_lines}")
    print(
        "category_counts="
        + str(dict(sorted(Counter(item.category for item in selections).items(), key=lambda kv: int(kv[0]))))
    )
    print(f"output={args.output_csv}")
    for line_id, item in enumerate(selections, start=1):
        print(f"{line_id}\t{item.language}\t{item.repo}\t{item.build_id}\tlines={item.line_count}")


if __name__ == "__main__":
    main()
