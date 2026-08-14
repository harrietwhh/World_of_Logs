# Uncertainty <= 0.20 eval report

Generated from:

```bash
python3 rq2.1/eval/scripts/uncertainty_eval_log_msg.py --thresholds 0.20
```

Inference blocks are kept only when `pred_uncertainty` is numeric and
`<= 0.20`. GT is not filtered.

Eval setup:
- Exact match uses the same text-only normalization as basic eval, ignoring
  whitespace, newlines, and separator punctuation.
- Relaxed match uses the same one-to-one token-F1 >= 0.8 rule as basic eval.
- GT extraction, `gt_not_sure` filtering, log-message splitting, boundary
  repair, and block/message deduplication are unchanged from basic eval.

## summary

| source | evaluated | kept blocks | discarded > threshold | discarded missing | exact F1 | relaxed F1 | relaxed P | relaxed R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| github | 196 | 138 | 56 | 0 | 0.5227 | 0.7136 | 0.7734 | 0.6624 |
| jira | 175 | 127 | 34 | 0 | 0.4143 | 0.6190 | 0.7143 | 0.5462 |
| so | 197 | 88 | 81 | 0 | 0.3028 | 0.4312 | 0.7705 | 0.2994 |
| cc | 179 | 75 | 43 | 3 | 0.4643 | 0.5625 | 0.5727 | 0.5526 |

## basic-setting comparison

| source | basic-setting relaxed F1 | threshold relaxed F1 | delta |
|---|---:|---:|---:|
| github | 0.7421 | 0.7136 | -0.0284 |
| jira | 0.6996 | 0.6190 | -0.0805 |
| so | 0.5602 | 0.4312 | -0.1290 |
| cc | 0.5455 | 0.5625 | +0.0170 |
