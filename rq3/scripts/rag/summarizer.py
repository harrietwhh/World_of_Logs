#!/usr/bin/env python3
"""Filter and summarize retrieved external knowledge for one RQ3 case."""

import argparse
import json
import re
import textwrap
from pathlib import Path

try:
    from ..api_router import get_chat_completion
except ImportError:  # Running directly: python scripts/rag/summarizer.py
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from api_router import get_chat_completion


def build_prompt(group_logs: str, candidates: str) -> str:
    """Build the filtering and summarization prompt."""
    return textwrap.dedent(
        f"""
        You are a summarizer agent. You are given:
        1. A group of software log lines from one case.
        2. A set of retrieved external developer discussions.

        Your task:
        - Keep only the retrieved items that are relevant to this case.
        - Prefer items that mention similar symptoms, failure modes, components, causes, or remediation clues.
        - Remove items that are only lexically similar but not actually useful.
        - Then write a short factual summary of the useful external knowledge.

        Requirements:
        - Do not explain the whole case yet.
        - Do not invent facts that are not supported by the retrieved text.
        - Keep the summary traceable to the retrieved evidence.
        - Keep the summary concise and easy to understand.
        - Do not add narrative or commentary outside the requested output format.
        - If almost nothing is relevant, say so clearly.
        - If no retrieved item is relevant, write:
          Filtered Relevant Items: None
          External Knowledge Summary: No relevant external knowledge was found.

        Log group:
        {group_logs}

        Retrieved external developer discussions:
        {candidates}

        Output format:

        Filtered Relevant Items:
        1. <item>
        2. <item>

        External Knowledge Summary:
        - <finding 1>
        - <finding 2>
        - <finding 3>
        """
    ).strip()


def build_messages(group_logs: str, candidates: str) -> list[dict[str, str]]:
    """Build the single system message sent to the Azure OpenAI model."""
    return [{"role": "system", "content": build_prompt(group_logs, candidates)}]


def _load_group_logs(path: Path) -> tuple[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    case_id = str(payload.get("case_id", ""))
    lines = payload.get("group_logs_lines", [])
    if isinstance(lines, list):
        group_logs = "\n".join(str(line) for line in lines)
    else:
        group_logs = str(payload.get("group_logs", lines or ""))
    if not group_logs.strip():
        raise ValueError(f"No group logs found in {path}")
    return case_id, group_logs


def _load_candidates(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected a candidate list in {path}")

    formatted = []
    for index, candidate in enumerate(payload, start=1):
        if isinstance(candidate, dict):
            text = str(candidate.get("text", "")).strip()
            rank = candidate.get("rank", index)
        else:
            text = str(candidate).strip()
            rank = index
        if text:
            formatted.append(f"[{rank}]\n{text}")
    return "\n\n".join(formatted) or "No retrieved discussions were provided."


def _extract_summary(response: str) -> str:
    match = re.search(
        r"External Knowledge Summary:\s*(.*?)(?:\n\s*\Z|\Z)",
        response,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return (match.group(1).strip() if match else response.strip())


def run_summarizer(
    case_input: Path,
    retrieved_candidates: Path,
    output_dir: Path,
) -> str:
    """Run one model request and save the raw response and extracted summary in JSON."""
    case_id, group_logs = _load_group_logs(case_input)
    candidates = _load_candidates(retrieved_candidates)
    response = get_chat_completion(build_messages(group_logs, candidates))

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summarizer_result.json").write_text(
        json.dumps(
            {
                "case_id": case_id,
                "case_input": str(case_input),
                "retrieved_candidates": str(retrieved_candidates),
                "response": response,
                "external_knowledge_summary": _extract_summary(response),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return response


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-input", type=Path, required=True)
    parser.add_argument("--retrieved-candidates", type=Path, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory; defaults to summarizer_results/<retrieval-case-dir>.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output_dir:
        output_dir = args.output_dir
    else:
        # Keep each case separate while placing all default results under one root.
        retrieval_group = args.retrieved_candidates.parent.parent.name
        retrieval_case = args.retrieved_candidates.parent.name
        project = retrieval_group.removesuffix("_intermediate_group_logs")
        case = retrieval_case.removesuffix("_group_logs")
        output_dir = Path("summarizer_results") / project / case
    run_summarizer(args.case_input, args.retrieved_candidates, output_dir)
    print(f"Wrote summarization artifacts to {output_dir}")


if __name__ == "__main__":
    main()
