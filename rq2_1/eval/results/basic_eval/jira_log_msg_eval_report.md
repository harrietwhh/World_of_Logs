# jira log-message eval report

Generated from:

```bash
python3 rq2.1/eval/scripts/basic_eval_log_msg.py --source jira --out-dir rq2.1/eval/results/basic_eval
```

Input:
- `rq2.1/eval/data/jira_audit_sample.csv`

Outputs:
- `rq2.1/eval/results/basic_eval/jira_log_msg_eval.csv`
- `rq2.1/eval/results/basic_eval/jira_log_msg_eval_summary.json`

## eval setup

- Evaluation level: log message level.
- GT source: `<log>...</log>` spans from joined `gt_*` annotation columns.
- `gt_not_sure == 1` samples are skipped.
- Log blocks and message lists are deduplicated within each side before comparison.
- Non-timestamp boundary repair is enabled for log-like starts.
- Exact comparison uses text-only normalization.
- Relaxed comparison uses one-to-one token-F1 matching with threshold `0.8`.

## skipped samples

Skipped because `gt_not_sure == 1`:
- `jira_positive_doc_0001`
- `jira_positive_doc_0013`
- `jira_positive_doc_0015`
- `jira_positive_doc_0016`
- `jira_positive_doc_0019`
- `jira_positive_doc_0024`
- `jira_positive_doc_0029`
- `jira_positive_doc_0030`
- `jira_positive_doc_0036`
- `jira_positive_doc_0037`
- `jira_positive_doc_0040`
- `jira_positive_doc_0052`
- `jira_positive_doc_0059`
- `jira_positive_doc_0061`
- `jira_positive_doc_0067`
- `jira_positive_doc_0069`
- `jira_positive_doc_0070`
- `jira_positive_doc_0073`
- `jira_positive_doc_0074`
- `jira_positive_doc_0077`
- `jira_positive_doc_0084`
- `jira_positive_doc_0088`
- `jira_positive_doc_0093`
- `jira_positive_doc_0094`
- `jira_positive_doc_0096`

## summary

| metric | exact | relaxed |
|---|---:|---:|
| matched rows | 115 | 131 |
| mismatch rows | 60 | 44 |
| total TP | 120 | 170 |
| total FP | 128 | 78 |
| total FN | 118 | 68 |
| precision | 0.4839 | 0.6855 |
| recall | 0.5042 | 0.7143 |
| F1 | 0.4938 | 0.6996 |

Other counts:
- total rows: 200
- evaluated rows: 175
- skipped rows: 25

## row-level match counts

| sample type | skipped | exact-match rows | relaxed-match rows | exact mismatch rows | relaxed mismatch rows |
|---|---:|---:|---:|---:|---:|
| negative_doc | 0 | 97 | 97 | 3 | 3 |
| positive_doc | 25 | 18 | 34 | 57 | 41 |

## notes

- Relaxed matching fixes 16 evaluated samples that fail exact matching.
- Detailed per-sample messages and mismatch lists are in the CSV output.
