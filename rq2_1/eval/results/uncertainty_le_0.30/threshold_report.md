# Uncertainty <= 0.30 eval report

Generated from:

```bash
python3 rq2.1/eval/scripts/uncertainty_eval_log_msg.py --thresholds 0.30
```

Inference blocks are kept only when `pred_uncertainty` is numeric and
`<= 0.30`. GT is not filtered.

Eval setup:
- Exact match uses the same text-only normalization as basic eval, ignoring
  whitespace, newlines, and separator punctuation.
- Relaxed match uses the same one-to-one token-F1 >= 0.8 rule as basic eval.
- GT extraction, `gt_not_sure` filtering, log-message splitting, boundary
  repair, and block/message deduplication are unchanged from basic eval.

## summary

| source | evaluated | kept blocks | discarded > threshold | discarded missing | exact F1 | relaxed F1 | relaxed P | relaxed R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| github | 196 | 167 | 27 | 0 | 0.5265 | 0.7176 | 0.7222 | 0.7131 |
| jira | 175 | 140 | 21 | 0 | 0.4588 | 0.6682 | 0.7109 | 0.6303 |
| so | 197 | 125 | 44 | 0 | 0.2947 | 0.4758 | 0.7019 | 0.3599 |
| cc | 179 | 80 | 38 | 3 | 0.4716 | 0.5764 | 0.5739 | 0.5789 |

## basic-setting comparison

| source | basic-setting relaxed F1 | threshold relaxed F1 | delta |
|---|---:|---:|---:|
| github | 0.7421 | 0.7176 | -0.0244 |
| jira | 0.6996 | 0.6682 | -0.0314 |
| so | 0.5602 | 0.4758 | -0.0844 |
| cc | 0.5455 | 0.5764 | +0.0310 |
