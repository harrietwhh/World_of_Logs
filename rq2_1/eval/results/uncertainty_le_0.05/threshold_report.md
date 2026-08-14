# Uncertainty <= 0.05 eval report

Generated from:

```bash
python3 rq2.1/eval/scripts/uncertainty_eval_log_msg.py --thresholds 0.05
```

Inference blocks are kept only when `pred_uncertainty` is numeric and
`<= 0.05`. GT is not filtered.

Eval setup:
- Exact match uses the same text-only normalization as basic eval, ignoring
  whitespace, newlines, and separator punctuation.
- Relaxed match uses the same one-to-one token-F1 >= 0.8 rule as basic eval.
- GT extraction, `gt_not_sure` filtering, log-message splitting, boundary
  repair, and block/message deduplication are unchanged from basic eval.

## summary

| source | evaluated | kept blocks | discarded > threshold | discarded missing | exact F1 | relaxed F1 | relaxed P | relaxed R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| github | 196 | 107 | 87 | 0 | 0.4496 | 0.5943 | 0.7667 | 0.4852 |
| jira | 175 | 105 | 56 | 0 | 0.3289 | 0.5040 | 0.6835 | 0.3992 |
| so | 197 | 68 | 101 | 0 | 0.2481 | 0.3623 | 0.8202 | 0.2325 |
| cc | 179 | 26 | 92 | 3 | 0.3733 | 0.4000 | 0.8333 | 0.2632 |

## basic-setting comparison

| source | basic-setting relaxed F1 | threshold relaxed F1 | delta |
|---|---:|---:|---:|
| github | 0.7421 | 0.5943 | -0.1477 |
| jira | 0.6996 | 0.5040 | -0.1956 |
| so | 0.5602 | 0.3623 | -0.1979 |
| cc | 0.5455 | 0.4000 | -0.1455 |
