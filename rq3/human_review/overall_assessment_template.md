# Overall Human-Review Assessment

- Results reviewed: `<number>` of `<total>`
- Projects/datasets covered: `<...>`

## Aggregate judgments

| Field | Correct | Partially correct | Incorrect | Unable to determine |
|---|---:|---:|---:|---:|
| Filtered Relevant Items | `<n>` | `<n>` | `<n>` | `<n>` |
| `external_knowledge_summary` | `<n>` | `<n>` | `<n>` | `<n>` |

## Reliability assessment

Overall reliability of the generated summarizer results:

`<Reliable / Mostly reliable / Questionable / Unreliable>`

Evidence supporting this assessment:

`<Summarize the recurring strengths, weaknesses, and the evidence behind the overall rating.>`

## False positives

List three representative retained retrieval results that were irrelevant or weakly related.

| Project/case | Retained item | Why it is a false positive | Recurring pattern? |
|---|---|---|---|
| `<project>/case_<id>` | `<item>` | `<evidence-based explanation>` | `<yes / no>` |

## False negatives

List three representative relevant retrieval results that were incorrectly omitted.

| Project/case | Omitted item | Why it is a false negative | Recurring pattern? |
|---|---|---|---|
| `<project>/case_<id>` | `<item>` | `<evidence-based explanation>` | `<yes / no>` |

## Other incorrect judgments, omissions, or inconsistencies

`<Describe evidence-backed issues that are not captured by the false-positive or false-negative tables.>`

## Recurring error patterns

- `<pattern 1>`
- `<pattern 2>`
- `<pattern 3>`

## Recommended follow-up

- Prompt changes: `<...>`
- Changes to `scripts/rag/summarizer.py`: `<...>`
- Additional review or adjudication needed: `<...>`
