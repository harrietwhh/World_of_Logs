# cc log-message eval report

Generated from:

```bash
python3 rq2.1/eval/scripts/basic_eval_log_msg.py --source cc --out-dir rq2.1/eval/results/basic_eval
```

Input:
- `rq2.1/eval/data/cc_audit_sample.csv`

Outputs:
- `rq2.1/eval/results/basic_eval/cc_log_msg_eval.csv`
- `rq2.1/eval/results/basic_eval/cc_log_msg_eval_summary.json`

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
- `common_crawl_positive_doc_0006`
- `common_crawl_positive_doc_0020`
- `common_crawl_positive_doc_0026`
- `common_crawl_positive_doc_0028`
- `common_crawl_positive_doc_0035`
- `common_crawl_positive_doc_0039`
- `common_crawl_positive_doc_0047`
- `common_crawl_positive_doc_0054`
- `common_crawl_positive_doc_0061`
- `common_crawl_positive_doc_0066`
- `common_crawl_positive_doc_0068`
- `common_crawl_positive_doc_0070`
- `common_crawl_positive_doc_0075`
- `common_crawl_positive_doc_0080`
- `common_crawl_positive_doc_0081`
- `common_crawl_positive_doc_0083`
- `common_crawl_positive_doc_0094`
- `common_crawl_positive_doc_0095`
- `common_crawl_positive_doc_0096`
- `common_crawl_negative_doc_0079`
- `common_crawl_negative_doc_0080`

## summary

| metric | exact | relaxed |
|---|---:|---:|
| matched rows | 127 | 135 |
| mismatch rows | 52 | 44 |
| total TP | 59 | 75 |
| total FP | 102 | 86 |
| total FN | 55 | 39 |
| precision | 0.3665 | 0.4658 |
| recall | 0.5175 | 0.6579 |
| F1 | 0.4291 | 0.5455 |

Other counts:
- total rows: 200
- evaluated rows: 179
- skipped rows: 21

## row-level match counts

| sample type | skipped | exact-match rows | relaxed-match rows | exact mismatch rows | relaxed mismatch rows |
|---|---:|---:|---:|---:|---:|
| negative_doc | 2 | 98 | 98 | 0 | 0 |
| positive_doc | 19 | 29 | 37 | 52 | 44 |

## notes

- Relaxed matching fixes 8 evaluated samples that fail exact matching.
- Detailed per-sample messages and mismatch lists are in the CSV output.
