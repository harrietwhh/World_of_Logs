# Uncertainty <= 0.40 eval report

Generated from:

```bash
python3 rq2.1/eval/scripts/uncertainty_eval_log_msg.py --thresholds 0.40
```

Inference blocks are kept only when `pred_uncertainty` is numeric and
`<= 0.40`. GT is not filtered.

Eval setup:
- Exact match uses the same text-only normalization as basic eval, ignoring
  whitespace, newlines, and separator punctuation.
- Relaxed match uses the same one-to-one token-F1 >= 0.8 rule as basic eval.
- GT extraction, `gt_not_sure` filtering, log-message splitting, boundary
  repair, and block/message deduplication are unchanged from basic eval.

## summary

| source | evaluated | kept blocks | discarded > threshold | discarded missing | exact F1 | relaxed F1 | relaxed P | relaxed R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| github | 196 | 184 | 10 | 0 | 0.5466 | 0.7368 | 0.7082 | 0.7679 |
| jira | 175 | 145 | 16 | 0 | 0.4947 | 0.6951 | 0.7056 | 0.6849 |
| so | 197 | 136 | 33 | 0 | 0.3074 | 0.4959 | 0.6954 | 0.3854 |
| cc | 179 | 94 | 24 | 3 | 0.4490 | 0.5551 | 0.5191 | 0.5965 |

## basic-setting comparison

| source | basic-setting relaxed F1 | threshold relaxed F1 | delta |
|---|---:|---:|---:|
| github | 0.7421 | 0.7368 | -0.0052 |
| jira | 0.6996 | 0.6951 | -0.0045 |
| so | 0.5602 | 0.4959 | -0.0642 |
| cc | 0.5455 | 0.5551 | +0.0096 |
