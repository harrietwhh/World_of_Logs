# Human Review: `<project>/case_<id>`

- Reviewer: `<name>`
- Review date: `<YYYY-MM-DD>`
- Summarizer result: `summarizer_results/<project>/case_<id>/summarizer_result.json`
- Original log sequence: `<path or identifier>`
- Retrieval result: `<path or identifier>`

## 1. Filtered Relevant Items

### Judgment

- [ ] Correct
- [ ] Partially correct
- [ ] Incorrect
- [ ] Unable to determine

### Retained items

List every item retained after `Filtered Relevant Items:`.

| Item or retrieval-result ID | Relevant to the original log sequence? | Evidence | Judgment |
|---|---|---|---|
| `<item>` | `<yes / partly / no>` | `<log or retrieval evidence>` | `<correct / false positive>` |

### False positives (if applicable)

A false positive is a retained retrieval result that is irrelevant or weakly related.

| Retained item | Why it is irrelevant or weakly related | Evidence |
|---|---|---|
| `<item or None>` | `<explanation>` | `<source evidence>` |

### False negatives (if applicable)

A false negative is a relevant retrieval result that was incorrectly omitted.

| Omitted relevant item | Why it should have been retained | Evidence |
|---|---|---|
| `<item or None>` | `<explanation>` | `<source evidence>` |

### Notes on omissions or inconsistencies (if applicable)

`<Describe missing, duplicated, contradictory, or incorrectly identified items.>`

## 2. `external_knowledge_summary`

### Judgment

- [ ] Correct
- [ ] Partially correct
- [ ] Incorrect
- [ ] Unable to determine

### Evidence-based assessment

- Claims supported by the log sequence: `<...>`
- Claims supported by the retained retrieval results: `<...>`
- Unsupported or contradictory claims: `<None or details>`
- Important omitted information: `<None or details>`
- Clarity and consistency with `Filtered Relevant Items`: `<assessment>`

### Incorrect judgments, omissions, or inconsistencies (if applicable)

| Summary statement or omission | Expected assessment | Evidence |
|---|---|---|
| `<statement or omission>` | `<what should be stated or omitted>` | `<source evidence>` |

## 3. Per-file conclusion

- Overall file reliability: `<Reliable / Mostly reliable / Questionable / Unreliable>`
- Main reason: `<one or two sentences>`
- Representative false positives: `<list or None>`
- Representative false negatives: `<list or None>`
- Follow-up needed in `scripts/rag/summarizer.py` or prompt/output handling: `<yes / no; details>`
