# so log-message eval report

Generated from:

```bash
python3 rq2.1/eval/scripts/basic_eval_log_msg.py --source so --out-dir rq2.1/eval/results/basic_eval
```

Input:
- `rq2.1/eval/data/so_audit_sample.csv`

Outputs:
- `rq2.1/eval/results/basic_eval/so_log_msg_eval.csv`
- `rq2.1/eval/results/basic_eval/so_log_msg_eval_summary.json`

## eval setup

- Evaluation level: log message level.
- GT source: `<log>...</log>` spans from joined `gt_*` annotation columns.
- `gt_not_sure == 1` samples are skipped.
- Message lists are deduplicated within each side before comparison.
- Non-timestamp boundary repair is enabled for log-like starts.
- Exact comparison uses text-only normalization.
- Relaxed comparison uses one-to-one token-F1 matching with threshold `0.8`.

## skipped samples

Skipped because `gt_not_sure == 1`:
- `stack_overflow_positive_doc_0021`
- `stack_overflow_positive_doc_0077`
- `stack_overflow_positive_doc_0099`

## summary

| metric | exact | relaxed |
|---|---:|---:|
| matched rows | 115 | 126 |
| mismatch rows | 82 | 71 |
| total TP | 95 | 149 |
| total FP | 123 | 69 |
| total FN | 219 | 165 |
| precision | 0.4358 | 0.6835 |
| recall | 0.3025 | 0.4745 |
| F1 | 0.3571 | 0.5602 |

Other counts:
- total rows: 200
- evaluated rows: 197
- skipped rows: 3

## row-level match counts

| sample type | skipped | exact-match rows | relaxed-match rows | exact mismatch rows | relaxed mismatch rows |
|---|---:|---:|---:|---:|---:|
| negative_doc | 0 | 90 | 90 | 10 | 10 |
| positive_doc | 3 | 25 | 36 | 72 | 61 |

## notes

- Relaxed matching fixes 11 evaluated samples that fail exact matching.
- Detailed per-sample messages and mismatch lists are in the CSV output.
