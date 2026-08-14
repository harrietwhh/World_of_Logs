# github log-message eval report

Generated from:

```bash
python3 rq2.1/eval/scripts/basic_eval_log_msg.py --source github --out-dir rq2.1/eval/results/basic_eval
```

Input:
- `rq2.1/eval/data/github_audit_sample.csv`

Outputs:
- `rq2.1/eval/results/basic_eval/github_log_msg_eval.csv`
- `rq2.1/eval/results/basic_eval/github_log_msg_eval_summary.json`

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
- `github_positive_doc_0013`
- `github_positive_doc_0024`
- `github_positive_doc_0032`
- `github_positive_doc_0068`

## summary

| metric | exact | relaxed |
|---|---:|---:|
| matched rows | 131 | 151 |
| mismatch rows | 65 | 45 |
| total TP | 137 | 187 |
| total FP | 130 | 80 |
| total FN | 100 | 50 |
| precision | 0.5131 | 0.7004 |
| recall | 0.5781 | 0.7890 |
| F1 | 0.5437 | 0.7421 |

Other counts:
- total rows: 200
- evaluated rows: 196
- skipped rows: 4

## row-level match counts

| sample type | skipped | exact-match rows | relaxed-match rows | exact mismatch rows | relaxed mismatch rows |
|---|---:|---:|---:|---:|---:|
| negative_doc | 0 | 98 | 98 | 2 | 2 |
| positive_doc | 4 | 33 | 53 | 63 | 43 |

## notes

- Relaxed matching fixes 20 evaluated samples that fail exact matching.
- Detailed per-sample messages and mismatch lists are in the CSV output.
