## scripts for sampling

### Audit sample CSV for manual annotation

Script:
- `sample_audit_docs.py`
- `utils.py`
- `source_jira.py`
- `source_github.py`
- `source_so.py`
- `source_common_crawl.py`
- `source_cc_neg_patch.py`

Goal:
- sample RQ2.1 `v2` MongoDB documents directly for manual audit
- export one compact CSV per source
- save the MongoDB query/projection/random seed to a JSON metadata file

Note on compact source-specific CSVs:
- The script writes one CSV for each selected source.
- Each source keeps its own source-specific metadata column:
  - JIRA: `sample_id, source, sample_type, doc_id, url, project, issue_key, created_at, pred_uncertainty, has_log_msg_desc, has_log_msg_comm, log_blks, log_blks_comments, issue_description, comment_bodies`
  - GitHub: `sample_id, source, sample_type, doc_id, url, repo, created_at, pred_uncertainty, has_log_msg_desc, has_log_msg_comm, log_blks, log_blks_comments, issue_title, issue_description, comment_bodies`
  - Stack Overflow: `sample_id, source, sample_type, doc_id, url, tag, created_at, pred_uncertainty, has_log_msg_desc, has_log_msg_comm, log_blks, log_blks_answers, question_description, answer_descriptions`
  - Common Crawl: `sample_id, source, sample_type, doc_id, url, created_at, pred_uncertainty, has_log_msg, log_blks, log_msgs, page_description, dump_version, imported_at`
- "compact" means each CSV keeps only fields needed for manual audit, not every original MongoDB field.

Code layout:
- `sample_audit_docs.py`: CLI entry point and sampling orchestration
- `utils.py`: common MongoDB query builders, random sampling, CSV/metadata writers, and value normalization
- `source_jira.py`: JIRA collections and field mapping
- `source_github.py`: GitHub collections and field mapping
- `source_so.py`: Stack Overflow collections and field mapping
- `source_common_crawl.py`: Common Crawl collections and field mapping
- `source_cc_neg_patch.py`: standalone Common Crawl negative-only sampler for the separate negative-pool machine

Sampling logic:
- `positive_doc`: documents where `has_log_msg_desc == true` or `has_log_msg_comm == true`
- `negative_doc`: documents where neither `has_log_msg_desc` nor `has_log_msg_comm` is true
- Common Crawl uses `has_log_msg == true` for `positive_doc`; `negative_doc` excludes docs where `has_log_msg == true` or `log_blks` contains an extracted block.
- default sample size is `100` positive docs and `100` negative docs per source
- `created_since` is inclusive and is applied as MongoDB `$gte`
- JIRA uses `created_at >= 2022-01-06`
- Stack Overflow uses `created_at/created/... >= 2025-07-01`
- sampling uses seeded random + count-weighted skip, so the sample is reproducible when the database state and query result ordering are unchanged
- for `negative_doc` without `created_since`, count is estimated as `estimated_document_count() - positive_count` to avoid slow full negative counts on non-indexed predicates

Random seed:
- The seed is not applied to a document field such as `_id`.
- For each source and sample type, the script first computes a count used as sampling weight:
  - default: `count_documents(query)`
  - `negative_doc` with no `created_since`: `estimated_document_count() - count_documents(positive_query)`
- The seeded random generator then chooses:
  1. which collection to sample from, weighted by each collection's matching document count
  2. a random integer offset in `[0, count)`
- The selected document is read with `find(query, projection).skip(offset).limit(1)`.
- This means a 256-bit hash `_id` is retained as a document identifier, but it is not used as the sampling key.

Default field normalization:
- URL: `url`, `unique_url`, `html_url`, or `link`
- created time: `created_at`, `created`, `creation_date`, `timestamp`, or `crawl_timestamp`
- log block: `log_blks`, `log_blks_answers`, or `log_blks_comments`
- uncertainty: `pred_uncertainty`, `uncertainty`, or `avg_pred_uncertainty`

Stack Overflow schema mapping:
- doc id: `id`, `key`, or `_id`
- URL: `unique_url`
- tag: `fields.tags`
- created time: `created_at` or `fields.created`
- log block candidate fields: `log_blks`, `log_blks_answers`
- uncertainty: `pred_uncertainty`
- sampling flags: `has_log_msg_desc`, `has_log_msg_comm`
- question-side extracted logs: `log_blks`, exported as `log_blks`
- answer-side extracted logs: `log_blks_answers`, exported as JSON in `log_blks_answers`
- original question text: `fields.description`, exported as `question_description`
- original answer text: `answers.description`, exported as JSON list in `answer_descriptions`

JIRA schema mapping:
- doc id: `key`, `id`, `doc_id`, `issue_id`, or `_id`
- URL: `unique_url`, `url`, `self`, or `link`
- project: `source.project`
- created time: `created_at`
- log block candidate fields: `log_blks`, `log_blks_comments`
- uncertainty: `pred_uncertainty`, `uncertainty`, or `avg_pred_uncertainty`
- sampling flags: `has_log_msg_desc`, `has_log_msg_comm`
- issue-side extracted logs: `log_blks`, exported as `log_blks`
- comment-side extracted logs: `log_blks_comments`, exported as JSON in `log_blks_comments`
- original issue text: `fields.description`, exported as `issue_description`
- original comment text: `fields.comments.body`, exported as JSON list in `comment_bodies`

GitHub schema mapping:
- default DB/collection: `GitHub_v2.comments`
- doc id: `key` or `_id`
- URL: `unique_url`
- repo: `fields.repo`
- created time: `created_at` or `fields.created`
- log block candidate fields: `log_blks`, `log_blks_comments`
- uncertainty: `pred_uncertainty`
- sampling flags: `has_log_msg_desc`, `has_log_msg_comm`
- issue-side extracted logs: `log_blks`, exported as `log_blks`
- comment-side extracted logs: `log_blks_comments`, exported as JSON in `log_blks_comments`
- original issue title: `fields.title`, exported as `issue_title`
- original issue text: `fields.description`, exported as `issue_description`
- original comment text: `comments.body`, exported as JSON list in `comment_bodies`

Common Crawl schema mapping:
- default DB/collection: `CommonCrawl_v2.English`
- doc id: `_id`
- URL: `unique_url`
- created time: `fields.collected_at` or `source.imported_at`
- log block candidate field: `log_blks`
- uncertainty: `pred_uncertainty`
- sampling flag: `has_log_msg`
- extracted logs: `log_blks`, exported as `log_blks`
- extracted log message list: `log_msgs`, exported as JSON in `log_msgs`
- original page text: `fields.description`, exported as `page_description`
- dump version: `source.dump_version`, exported as `dump_version`
- import time: `source.imported_at`, exported as `imported_at`

Example:

```bash
python3 paper1_rq2/rq2.1/scripts/sample_audit_docs.py \
  --mongo-port 27017 \
  --sources jira \
  --seed 20260505 \
  --positive-per-source 100 \
  --negative-per-source 100
```

Output:
- `RQ2/rq2.1/dataset/audit_samples/jira_audit_sample.csv`
- `RQ2/rq2.1/dataset/audit_samples/so_audit_sample.csv`
- `RQ2/rq2.1/dataset/rq2_1_sampling_metadata.json`

GitHub and Common Crawl now have their own source files too. If the actual DB
or collection names differ from the defaults in those files, add a JSON config
and pass `--source-config-json`.

Example config:

```json
{
  "github": {
    "db": "GitHub_v2",
    "collections": ["comments"]
  },
  "cc": {
    "db": "CommonCrawl_v2",
    "collections": ["English"]
  }
}
```

Then run:

```bash
python3 RQ2/rq2.1/scripts/sample_audit_docs.py \
  --sources jira github so cc \
  --source-config-json RQ2/rq2.1/scripts/source_config.example.json
```

Common Crawl negative-only patch (run on Mac):

```bash
python3 RQ2/rq2.1/scripts/source_cc_neg_patch.py \
  --mongo-port 27017 \
  --db CommonCrawl \
  --collections English \
  --sample-size 100 \
  --output RQ2/rq2.1/dataset/samples/cc_negative_patch.csv
```

If the configured collection already contains only negative candidates, add
`--negative-pool-is-clean` so the script samples from the whole collection
instead of applying the `has_log_msg`/`log_blks` negative filter.

### JIRA

```
MONGO_PORT="27017"
TARGET_DB_NAME="JiraRepos_crawl_v2"
COLLECTIONS=(
    "Apache"
    "Jira"
    "JiraEcosystem"
    "MariaDB"
    "MongoDB"
    "Qt"
    "RedHat"
    "Sakai"
)
```

### SO

```
MONGO_PORT="27017"
TARGET_DB_NAME="SO_v2"
COLLECTIONS="SO_v2"
CREATED_SINCE="2025-07-01"
```
