# RQ2.1 Existing Annotation Audit Report

This report uses only existing RQ2.1 data: joined audit CSVs, basic
log-message evaluation outputs, and the joined annotation columns
`gt_log_type`, `gt_not_sure`, and `gt_NB`. No additional manual annotation is
introduced here.

Important interpretation: the boundary numbers below are automatic proxies
derived from exact message-level FP/FN counts. They are useful for triage
and explanation, but they are not new human `boundary_quality` labels.

## Positive-Doc Confirmed-Log Rate

A positive document is counted as confirmed when it is not skipped by
`gt_not_sure` filtering and its existing GT annotation contains at least
one `<log>...</log>` block. This is the positive-side counterpart to the
negative-doc missed-log rate.

| Source | Positive evaluated | Confirmed-log docs | Confirmed-log rate | No-GT-log docs | No-GT-log rate |
|---|---|---|---|---|---|
| GitHub | 96 | 93 | 96.9% | 3 | 3.1% |
| Stack Overflow | 97 | 97 | 100.0% | 0 | 0.0% |
| Common Crawl | 81 | 68 | 84.0% | 13 | 16.0% |
| Overall | 274 | 258 | 94.2% | 16 | 5.8% |

## Negative-Doc Missed-Log Rate

A negative document is counted as a missed-log case when it is not skipped
by `not_sure` filtering and its existing GT annotation contains at least
one `<log>...</log>` block.

| Source | Negative sampled | Evaluated | Skipped not_sure | Missed-log docs | Missed-log rate |
|---|---|---|---|---|---|
| GitHub | 100 | 100 | 0 | 2 | 2.0% |
| Stack Overflow | 100 | 100 | 0 | 10 | 10.0% |
| Common Crawl | 100 | 98 | 2 | 0 | 0.0% |
| Overall | 300 | 298 | 2 | 12 | 4.0% |

### Missed Negative Documents

| Source | sample_id | GT blocks | GT messages | GT log_type | URL |
|---|---|---|---|---|---|
| GitHub | github_negative_doc_0066 | 2 | 2 | test_log | https://github.com/Microsoft/perfview/pull/530 |
| GitHub | github_negative_doc_0100 | 1 | 1 | log_in_NL | https://github.com/raisezhang/react-drag-listview/issues/31 |
| Stack Overflow | stack_overflow_negative_doc_0009 | 1 | 1 | logging_statement | https://stackoverflow.com/questions/79769482 |
| Stack Overflow | stack_overflow_negative_doc_0013 | 2 | 1 | logging_statement<br><br>logging_statement | https://stackoverflow.com/questions/79848923 |
| Stack Overflow | stack_overflow_negative_doc_0034 | 12 | 7 | logging_statement<br><br>logging_statement | https://stackoverflow.com/questions/79797321 |
| Stack Overflow | stack_overflow_negative_doc_0037 | 2 | 2 | log_in_NL<br>logging_statement | https://stackoverflow.com/questions/79714660 |
| Stack Overflow | stack_overflow_negative_doc_0040 | 2 | 2 | logging_statement | https://stackoverflow.com/questions/79804439 |
| Stack Overflow | stack_overflow_negative_doc_0042 | 1 | 1 | logging_statement | https://stackoverflow.com/questions/79852125 |
| Stack Overflow | stack_overflow_negative_doc_0085 | 1 | 1 | logging_statement | https://stackoverflow.com/questions/79776598 |
| Stack Overflow | stack_overflow_negative_doc_0094 | 1 | 1 | logging_statement | https://stackoverflow.com/questions/79732408 |
| Stack Overflow | stack_overflow_negative_doc_0098 | 2 | 4 | logging_statement | https://stackoverflow.com/questions/79776379 |
| Stack Overflow | stack_overflow_negative_doc_0099 | 1 | 1 | build_log | https://stackoverflow.com/questions/79870067 |

## Annotation-Derived Log-Type Evidence

The counts below come from the joined eval CSV `gt_log_type` column.
Multi-label cells are split on newlines and commas, so label occurrence
counts may exceed the number of rows.

| Source | sample_type | Rows | Rows with log_type | Top log_type labels |
|---|---|---|---|---|
| GitHub | positive_doc | 100 | 93 | error_message (35); stack_trace (34); logging_statement (14); build_log (12); execution_log (6); log_in_NL (5); test_log (3); Hardware_Detection_Log (1) |
| GitHub | negative_doc | 100 | 2 | test_log (1); log_in_NL (1) |
| Stack Overflow | positive_doc | 100 | 100 | logging_statement (51); build_log (16); console_log (15); exception (13); execution_log (12); log_in_NL (8); other (4); Configuration_Error (3) |
| Stack Overflow | negative_doc | 100 | 10 | logging_statement (11); log_in_NL (1); build_log (1) |
| Common Crawl | positive_doc | 100 | 83 | web_error_msg (34); php_err (30); execution_log (5); configuration_error_msg (5); db_error_msg (4); build_log (2); access_log (1); monitoring_log (1) |
| Common Crawl | negative_doc | 100 | 2 | web_error_msg (2) |

## not_sure Summary

This summary uses `gt_not_sure` from the joined eval CSV as the
authoritative value, because this is the field used by the existing
eval scripts for skipping rows.

| Source | sample_type | Rows | gt_not_sure rows | gt_not_sure rate |
|---|---|---|---|---|
| GitHub | positive_doc | 100 | 4 | 4.0% |
| GitHub | negative_doc | 100 | 0 | 0.0% |
| Stack Overflow | positive_doc | 100 | 3 | 3.0% |
| Stack Overflow | negative_doc | 100 | 0 | 0.0% |
| Common Crawl | positive_doc | 100 | 19 | 19.0% |
| Common Crawl | negative_doc | 100 | 2 | 2.0% |

## Common Crawl NB Notes

Only the Common Crawl joined eval CSV has a `gt_NB` column. These notes are
useful for explaining ambiguous web-page cases, especially prompts,
template/liquid errors, and boundary uncertainty.

| sample_id | sample_type | log_type | not_sure | NB |
|---|---|---|---|---|
| common_crawl_positive_doc_0002 | positive_doc | php_err |  | execution_log |
| common_crawl_positive_doc_0006 | positive_doc | no | 1 | It may or may not be taken into account. |
| common_crawl_positive_doc_0010 | positive_doc | no |  | health warnning msg; format similar to log pattern |
| common_crawl_positive_doc_0026 | positive_doc | no | 1 | It may or may not be taken into account. |
| common_crawl_positive_doc_0030 | positive_doc | no |  | prompt for users to take actions |
| common_crawl_positive_doc_0043 | positive_doc | no |  | prompt for users to take actions |
| common_crawl_positive_doc_0055 | positive_doc | web_error_msg |  | liquid error |
| common_crawl_positive_doc_0056 | positive_doc | web_error_msg | 0 | not sure log boundry |
| common_crawl_positive_doc_0059 | positive_doc | Installation_Error |  | Installation Error, Configuration Error, Excel VBA Runtime Error |
| common_crawl_positive_doc_0066 | positive_doc | build_log | 1 | issue title related to build logs |
| common_crawl_positive_doc_0067 | positive_doc | web_error_msg |  | liquid error |
| common_crawl_positive_doc_0068 | positive_doc | no | 1 | It may or may not be taken into account. |
| common_crawl_positive_doc_0070 | positive_doc | web_error_msg | 1 | prompt for users to take actions |
| common_crawl_positive_doc_0071 | positive_doc | execution_log, build_log |  | issue title related to logs |
| common_crawl_positive_doc_0074 | positive_doc | configuration_error_msg |  | issue title related to logs: Environment Error / Configuration Error |
| common_crawl_positive_doc_0075 | positive_doc | web_error_msg | 1 | prompt for users to take actions |
| common_crawl_positive_doc_0078 | positive_doc | no |  | prompt for users to take actions |
| common_crawl_positive_doc_0080 | positive_doc | web_error_msg | 1 | prompt for users to take actions |
| common_crawl_positive_doc_0081 | positive_doc | web_error_msg | 1 | prompt for users to take actions |
| common_crawl_positive_doc_0083 | positive_doc | web_error_msg | 1 | prompt for users to take actions |
| common_crawl_positive_doc_0094 | positive_doc | web_error_msg | 1 | prompt for users to take actions |
| common_crawl_positive_doc_0095 | positive_doc | err_msg | 1 | issue title related to logs |
| common_crawl_positive_doc_0096 | positive_doc | no | 1 | It may or may not be taken into account. |
| common_crawl_negative_doc_0079 | negative_doc | web_error_msg | 1 | prompt for users to take actions; template error |
| common_crawl_negative_doc_0080 | negative_doc | web_error_msg | 1 | prompt for users to take actions |

## Automatic Boundary Proxy

This table reuses existing exact message-level FP/FN counts on evaluated
positive documents. It should be described as an automatic proxy rather
than a manual exact/over/under boundary label.

| Source | Positive evaluated | Exact proxy | Over proxy | Under proxy | Mixed/wrong proxy | No GT log tag |
|---|---|---|---|---|---|---|
| GitHub | 96 | 32 (33.3%) | 0 (0.0%) | 4 (4.2%) | 57 (59.4%) | 3 (3.1%) |
| Stack Overflow | 97 | 25 (25.8%) | 2 (2.1%) | 5 (5.2%) | 65 (67.0%) | 0 (0.0%) |
| Common Crawl | 81 | 29 (35.8%) | 1 (1.2%) | 0 (0.0%) | 38 (46.9%) | 13 (16.0%) |

## Existing Basic Eval Reference

| Source | Evaluated rows | Exact P | Exact R | Exact F1 | Relaxed P | Relaxed R | Relaxed F1 |
|---|---|---|---|---|---|---|---|
| GitHub | 196 | 0.513 | 0.578 | 0.544 | 0.700 | 0.789 | 0.742 |
| Stack Overflow | 197 | 0.436 | 0.303 | 0.357 | 0.683 | 0.475 | 0.560 |
| Common Crawl | 179 | 0.366 | 0.518 | 0.429 | 0.466 | 0.658 | 0.545 |

## Paper-Use Notes

- The missed-log rate can be reported directly as an existing-annotation
  result for negative documents.
- The `log_type`, `not_sure`, and `NB` summaries can support qualitative
  explanation without adding new manual labels.
- The boundary proxy can motivate discussion, but the paper should avoid
  calling it a human `boundary_quality` annotation unless the text is
  revised to define it as an automatic message-level proxy.
