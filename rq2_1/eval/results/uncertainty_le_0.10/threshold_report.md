# Uncertainty <= 0.10 eval report

Generated from:

```bash
python3 rq2.1/eval/scripts/uncertainty_eval_log_msg.py --thresholds 0.10
```

Inference blocks are kept only when `pred_uncertainty` is numeric and
`<= 0.10`. GT is not filtered.

Eval setup:
- Exact match uses the same text-only normalization as basic eval, ignoring
  whitespace, newlines, and separator punctuation.
- Relaxed match uses the same one-to-one token-F1 >= 0.8 rule as basic eval.
- GT extraction, `gt_not_sure` filtering, log-message splitting, boundary
  repair, and block/message deduplication are unchanged from basic eval.

## summary

| source | evaluated | kept blocks | discarded > threshold | discarded missing | exact F1 | relaxed F1 | relaxed P | relaxed R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| github | 196 | 114 | 80 | 0 | 0.4467 | 0.6041 | 0.7580 | 0.5021 |
| jira | 175 | 114 | 47 | 0 | 0.3351 | 0.5361 | 0.6933 | 0.4370 |
| so | 197 | 79 | 90 | 0 | 0.2755 | 0.4038 | 0.7944 | 0.2707 |
| cc | 179 | 43 | 75 | 3 | 0.5083 | 0.5746 | 0.7761 | 0.4561 |

## basic-setting comparison

| source | basic-setting relaxed F1 | threshold relaxed F1 | delta |
|---|---:|---:|---:|
| github | 0.7421 | 0.6041 | -0.1380 |
| jira | 0.6996 | 0.5361 | -0.1635 |
| so | 0.5602 | 0.4038 | -0.1563 |
| cc | 0.5455 | 0.5746 | +0.0291 |
