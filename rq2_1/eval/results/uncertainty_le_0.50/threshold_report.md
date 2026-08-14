# Uncertainty <= 0.50 eval report

Generated from:

```bash
python3 rq2.1/eval/scripts/uncertainty_eval_log_msg.py --thresholds 0.50
```

Inference blocks are kept only when `pred_uncertainty` is numeric and
`<= 0.50`. GT is not filtered.

Eval setup:
- Exact match uses the same text-only normalization as basic eval, ignoring
  whitespace, newlines, and separator punctuation.
- Relaxed match uses the same one-to-one token-F1 >= 0.8 rule as basic eval.
- GT extraction, `gt_not_sure` filtering, log-message splitting, boundary
  repair, and block/message deduplication are unchanged from basic eval.

## summary

| source | evaluated | kept blocks | discarded > threshold | discarded missing | exact F1 | relaxed F1 | relaxed P | relaxed R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| github | 196 | 193 | 1 | 0 | 0.5447 | 0.7396 | 0.6992 | 0.7848 |
| jira | 175 | 160 | 1 | 0 | 0.4948 | 0.7010 | 0.6883 | 0.7143 |
| so | 197 | 167 | 2 | 0 | 0.3509 | 0.5547 | 0.6806 | 0.4682 |
| cc | 179 | 113 | 5 | 3 | 0.4135 | 0.5263 | 0.4605 | 0.6140 |

## basic-setting comparison

| source | basic-setting relaxed F1 | threshold relaxed F1 | delta |
|---|---:|---:|---:|
| github | 0.7421 | 0.7396 | -0.0025 |
| jira | 0.6996 | 0.7010 | +0.0014 |
| so | 0.5602 | 0.5547 | -0.0054 |
| cc | 0.5455 | 0.5263 | -0.0191 |
