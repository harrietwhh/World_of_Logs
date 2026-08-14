# Uncertainty-threshold comparison report

Basic setting (no filtering): `rq2.1/eval/results/basic_eval/`.

Thresholded outputs are stored under `uncertainty_le_<t>/` folders.

## eval setup

- The threshold only filters inference-side log blocks. GT is not filtered.
- Exact match is the same text-only exact match used in basic eval: normalize
  text and ignore non-text differences such as whitespace, newlines, and
  separator punctuation.
- Relaxed match is also the same as basic eval: one-to-one message matching
  with token-level F1 >= 0.8.
- GT extraction, `gt_not_sure` sample filtering, log-message splitting,
  boundary repair, and block/message deduplication are unchanged from basic eval.

## text-only exact F1 by source

Exact match here is the semantic text-only exact match from basic eval, not raw
string equality.

| source | basic setting | <=0.01 | <=0.05 | <=0.10 | <=0.20 | <=0.30 | <=0.40 | <=0.50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| github | 0.5437 | 0.4298 | 0.4496 | 0.4467 | 0.5227 | 0.5265 | 0.5466 | 0.5447 |
| jira | 0.4938 | 0.2985 | 0.3289 | 0.3351 | 0.4143 | 0.4588 | 0.4947 | 0.4948 |
| so | 0.3571 | 0.1183 | 0.2481 | 0.2755 | 0.3028 | 0.2947 | 0.3074 | 0.3509 |
| cc | 0.4291 | 0.2941 | 0.3733 | 0.5083 | 0.4643 | 0.4716 | 0.4490 | 0.4135 |

## relaxed F1 by source

| source | basic setting | <=0.01 | <=0.05 | <=0.10 | <=0.20 | <=0.30 | <=0.40 | <=0.50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| github | 0.7421 | 0.5510 | 0.5943 | 0.6041 | 0.7136 | 0.7176 | 0.7368 | 0.7396 |
| jira | 0.6996 | 0.4478 | 0.5040 | 0.5361 | 0.6190 | 0.6682 | 0.6951 | 0.7010 |
| so | 0.5602 | 0.1915 | 0.3623 | 0.4038 | 0.4312 | 0.4758 | 0.4959 | 0.5547 |
| cc | 0.5455 | 0.3088 | 0.4000 | 0.5746 | 0.5625 | 0.5764 | 0.5551 | 0.5263 |

## exact precision / recall by threshold

| threshold | source | kept blocks | discarded > threshold | discarded missing | exact P | exact R | exact F1 |
|---|---|---:|---:|---:|---:|---:|---:|
| <= 0.01 | github | 87 | 107 | 0 | 0.6190 | 0.3291 | 0.4298 |
| <= 0.01 | jira | 75 | 86 | 0 | 0.5155 | 0.2101 | 0.2985 |
| <= 0.01 | so | 35 | 134 | 0 | 0.5122 | 0.0669 | 0.1183 |
| <= 0.01 | cc | 15 | 103 | 3 | 0.9091 | 0.1754 | 0.2941 |
| <= 0.05 | github | 107 | 87 | 0 | 0.5800 | 0.3671 | 0.4496 |
| <= 0.05 | jira | 105 | 56 | 0 | 0.4460 | 0.2605 | 0.3289 |
| <= 0.05 | so | 68 | 101 | 0 | 0.5618 | 0.1592 | 0.2481 |
| <= 0.05 | cc | 26 | 92 | 3 | 0.7778 | 0.2456 | 0.3733 |
| <= 0.10 | github | 114 | 80 | 0 | 0.5605 | 0.3713 | 0.4467 |
| <= 0.10 | jira | 114 | 47 | 0 | 0.4333 | 0.2731 | 0.3351 |
| <= 0.10 | so | 79 | 90 | 0 | 0.5421 | 0.1847 | 0.2755 |
| <= 0.10 | cc | 43 | 75 | 3 | 0.6866 | 0.4035 | 0.5083 |
| <= 0.20 | github | 138 | 56 | 0 | 0.5665 | 0.4852 | 0.5227 |
| <= 0.20 | jira | 127 | 34 | 0 | 0.4780 | 0.3655 | 0.4143 |
| <= 0.20 | so | 88 | 81 | 0 | 0.5410 | 0.2102 | 0.3028 |
| <= 0.20 | cc | 75 | 43 | 3 | 0.4727 | 0.4561 | 0.4643 |
| <= 0.30 | github | 167 | 27 | 0 | 0.5299 | 0.5232 | 0.5265 |
| <= 0.30 | jira | 140 | 21 | 0 | 0.4882 | 0.4328 | 0.4588 |
| <= 0.30 | so | 125 | 44 | 0 | 0.4348 | 0.2229 | 0.2947 |
| <= 0.30 | cc | 80 | 38 | 3 | 0.4696 | 0.4737 | 0.4716 |
| <= 0.40 | github | 184 | 10 | 0 | 0.5253 | 0.5696 | 0.5466 |
| <= 0.40 | jira | 145 | 16 | 0 | 0.5022 | 0.4874 | 0.4947 |
| <= 0.40 | so | 136 | 33 | 0 | 0.4310 | 0.2389 | 0.3074 |
| <= 0.40 | cc | 94 | 24 | 3 | 0.4198 | 0.4825 | 0.4490 |
| <= 0.50 | github | 193 | 1 | 0 | 0.5150 | 0.5781 | 0.5447 |
| <= 0.50 | jira | 160 | 1 | 0 | 0.4858 | 0.5042 | 0.4948 |
| <= 0.50 | so | 167 | 2 | 0 | 0.4306 | 0.2962 | 0.3509 |
| <= 0.50 | cc | 113 | 5 | 3 | 0.3618 | 0.4825 | 0.4135 |

## relaxed precision / recall by threshold

| threshold | source | kept blocks | discarded > threshold | discarded missing | relaxed P | relaxed R | relaxed F1 |
|---|---|---:|---:|---:|---:|---:|---:|
| <= 0.01 | github | 87 | 107 | 0 | 0.7937 | 0.4219 | 0.5510 |
| <= 0.01 | jira | 75 | 86 | 0 | 0.7732 | 0.3151 | 0.4478 |
| <= 0.01 | so | 35 | 134 | 0 | 0.8293 | 0.1083 | 0.1915 |
| <= 0.01 | cc | 15 | 103 | 3 | 0.9545 | 0.1842 | 0.3088 |
| <= 0.05 | github | 107 | 87 | 0 | 0.7667 | 0.4852 | 0.5943 |
| <= 0.05 | jira | 105 | 56 | 0 | 0.6835 | 0.3992 | 0.5040 |
| <= 0.05 | so | 68 | 101 | 0 | 0.8202 | 0.2325 | 0.3623 |
| <= 0.05 | cc | 26 | 92 | 3 | 0.8333 | 0.2632 | 0.4000 |
| <= 0.10 | github | 114 | 80 | 0 | 0.7580 | 0.5021 | 0.6041 |
| <= 0.10 | jira | 114 | 47 | 0 | 0.6933 | 0.4370 | 0.5361 |
| <= 0.10 | so | 79 | 90 | 0 | 0.7944 | 0.2707 | 0.4038 |
| <= 0.10 | cc | 43 | 75 | 3 | 0.7761 | 0.4561 | 0.5746 |
| <= 0.20 | github | 138 | 56 | 0 | 0.7734 | 0.6624 | 0.7136 |
| <= 0.20 | jira | 127 | 34 | 0 | 0.7143 | 0.5462 | 0.6190 |
| <= 0.20 | so | 88 | 81 | 0 | 0.7705 | 0.2994 | 0.4312 |
| <= 0.20 | cc | 75 | 43 | 3 | 0.5727 | 0.5526 | 0.5625 |
| <= 0.30 | github | 167 | 27 | 0 | 0.7222 | 0.7131 | 0.7176 |
| <= 0.30 | jira | 140 | 21 | 0 | 0.7109 | 0.6303 | 0.6682 |
| <= 0.30 | so | 125 | 44 | 0 | 0.7019 | 0.3599 | 0.4758 |
| <= 0.30 | cc | 80 | 38 | 3 | 0.5739 | 0.5789 | 0.5764 |
| <= 0.40 | github | 184 | 10 | 0 | 0.7082 | 0.7679 | 0.7368 |
| <= 0.40 | jira | 145 | 16 | 0 | 0.7056 | 0.6849 | 0.6951 |
| <= 0.40 | so | 136 | 33 | 0 | 0.6954 | 0.3854 | 0.4959 |
| <= 0.40 | cc | 94 | 24 | 3 | 0.5191 | 0.5965 | 0.5551 |
| <= 0.50 | github | 193 | 1 | 0 | 0.6992 | 0.7848 | 0.7396 |
| <= 0.50 | jira | 160 | 1 | 0 | 0.6883 | 0.7143 | 0.7010 |
| <= 0.50 | so | 167 | 2 | 0 | 0.6806 | 0.4682 | 0.5547 |
| <= 0.50 | cc | 113 | 5 | 3 | 0.4605 | 0.6140 | 0.5263 |

## notes

- Lower thresholds keep fewer inference blocks, so precision may increase while recall drops.
- Blocks with missing or `NaN` uncertainty are excluded in thresholded runs.
- GT extraction and `gt_not_sure` filtering are unchanged from basic eval.
