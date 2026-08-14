#!/usr/bin/env python3
"""Run LLM-as-a-judge evaluation for generated log explanations."""

import argparse
import json
import re
from pathlib import Path

try:
    from .api_router import get_chat_completion
    from .prompt_templates import build_explanation_prompt, CRITERIA
except ImportError:  # Running directly: python scripts/llm_judge.py
    from api_router import get_chat_completion
    from prompt_templates import build_explanation_prompt, CRITERIA


system_prompt = (
    "You are an expert in system log analysis and incident explanation. "
)

template = f"""You are evaluating a generated explanation for a group of system log lines.
The explanation should be judged as a whole based on whether it is faithful to the evidence, covers the important incident information, helps an operator, and uses concrete log signals.

## Explanation Task and Evidence:
```
{{}}
```

## Explanation to Evaluate:
```
{{}}
```

Evaluate the explanation based on the following aspects:
{CRITERIA}

For each aspect, assign a score using the format `<Aspect>: X/5`.
After scoring each aspect, assign an overall score using the format `Overall: X/5` based on the average assessment of the explanation's quality.
"""


def temp_format(src: str, tgt: str):
    return template.format(src, tgt)


def build_messages(
    group_logs: str,
    external_info: str,
    explanation: str,
) -> list[dict[str, str]]:
    explanation_task = build_explanation_prompt(group_logs, external_info)
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": temp_format(explanation_task, explanation)},
    ]


def _case_key(record: dict) -> str:
    return f"{str(record.get('project', '')).strip()}:{str(record.get('case_id', '')).strip()}"


def _write_results(path: Path, results: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _safe_filename(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return safe.strip("_") or "unknown"


def _trajectory_path(input_json: Path, index: int, case_key: str) -> Path:
    filename = f"{input_json.stem}_{index:03d}_{_safe_filename(case_key)}.json"
    return Path("llm_judge/trajectory") / filename


def _write_trajectory(
    path: Path,
    *,
    input_json: Path,
    index: int,
    record: dict,
    messages: list[dict[str, str]],
    judge_response: str | None,
    error: str | None,
) -> None:
    payload = {
        "input_json": str(input_json),
        "record_index": index,
        "case_key": record.get("case_key") or _case_key(record),
        "project": str(record.get("project", "")).strip(),
        "case_id": str(record.get("case_id", "")).strip(),
        "messages": messages,
        "judge_response": judge_response,
        "error": error,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _load_records(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected {path} to contain a JSON list of explanation records")
    return data


def run_judge(input_json: Path, output_json: Path, limit: int | None = None) -> int:
    records = _load_records(input_json)
    if limit is not None:
        records = records[:limit]

    results: list[dict] = []
    for index, record in enumerate(records, start=1):
        project = str(record.get("project", "")).strip()
        case_id = str(record.get("case_id", "")).strip()
        group_logs = record.get("group_logs", "")
        external_info = record.get(
            "external_knowledge_summary",
            "No external information is provided.",
        )
        explanation = record.get("explanation")

        result = {
            "case_key": record.get("case_key") or _case_key(record),
            "project": project,
            "case_id": case_id,
            "judge_response": None,
            "error": None,
        }

        if not project or not case_id:
            result["error"] = f"Missing project/case_id at JSON record {index}"
        elif not isinstance(group_logs, str) or not group_logs.strip():
            result["error"] = f"Missing group_logs at JSON record {index}"
        elif not isinstance(explanation, str) or not explanation.strip():
            result["error"] = f"Missing explanation at JSON record {index}"
        else:
            messages = build_messages(group_logs, str(external_info), explanation)
            trajectory_path = _trajectory_path(input_json, index, result["case_key"])
            try:
                result["judge_response"] = get_chat_completion(messages)
            except Exception as exc:  # Keep completed judge results when one call fails.
                result["error"] = f"{type(exc).__name__}: {exc}"
            finally:
                _write_trajectory(
                    trajectory_path,
                    input_json=input_json,
                    index=index,
                    record=record,
                    messages=messages,
                    judge_response=result["judge_response"],
                    error=result["error"],
                )

        results.append(result)
        _write_results(output_json, results)
        print(f"[{index}/{len(records)}] {result['case_key']}")

    return len(results)


def default_output_path(input_json: Path) -> Path:
    return Path("llm_judge") / f"{input_json.stem}_judge.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-json",
        type=Path,
        required=True,
        help="JSON produced by baseline/run_baseline.py or rag/run_rag.py.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help="Output JSON path for judge responses. Defaults to llm_judge/<input_stem>_judge.json.",
    )
    parser.add_argument("--limit", type=int, help="Only process the first N records.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_json = args.output_json or default_output_path(args.input_json)
    count = run_judge(args.input_json, output_json, args.limit)
    print(f"Wrote {count} judge results to {output_json}")


if __name__ == "__main__":
    main()
