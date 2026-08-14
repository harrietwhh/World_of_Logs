# Uncertainty <= 0.01 eval report

Generated from:

```bash
python3 rq2.1/eval/scripts/uncertainty_eval_log_msg.py --thresholds 0.01
```

Inference blocks are kept only when `pred_uncertainty` is numeric and
`<= 0.01`. GT is not filtered.

Eval setup:
- Exact match uses the same text-only normalization as basic eval, ignoring
  whitespace, newlines, and separator punctuation.
- Relaxed match uses the same one-to-one token-F1 >= 0.8 rule as basic eval.
- GT extraction, `gt_not_sure` filtering, log-message splitting, boundary
  repair, and block/message deduplication are unchanged from basic eval.

## summary

| source | evaluated | kept blocks | discarded > threshold | discarded missing | exact F1 | relaxed F1 | relaxed P | relaxed R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| github | 196 | 87 | 107 | 0 | 0.4298 | 0.5510 | 0.7937 | 0.4219 |
| jira | 175 | 75 | 86 | 0 | 0.2985 | 0.4478 | 0.7732 | 0.3151 |
| so | 197 | 35 | 134 | 0 | 0.1183 | 0.1915 | 0.8293 | 0.1083 |
| cc | 179 | 15 | 103 | 3 | 0.2941 | 0.3088 | 0.9545 | 0.1842 |

## basic-setting comparison

| source | basic-setting relaxed F1 | threshold relaxed F1 | delta |
|---|---:|---:|---:|
| github | 0.7421 | 0.5510 | -0.1911 |
| jira | 0.6996 | 0.4478 | -0.2518 |
| so | 0.5602 | 0.1915 | -0.3686 |
| cc | 0.5455 | 0.3088 | -0.2366 |
