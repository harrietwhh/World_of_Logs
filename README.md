# Released Package

This repository contains the data, scripts, retrieval outputs, and evaluation results for the paper: Amassing and Indexing Web-Scale Logs from Web Pages: Towards the Census of Public Logs.

## Directory Overview

### `rq1/`

Materials for RQ1, including sampled log data and search results.

- `dataset/`: Sampled log data from several log categories, including build logs, logging statements, runtime logs, and testing logs.
- `scripts/`: Scripts for RQ1 sampling, Google search, and LogSearch queries.
- `search_results/`: Google and LogSearch retrieval outputs, including query manifests, batch metadata, log files, and normalized JSON results.

### `rq2_1/`

Materials for RQ2.1, including annotation data, inference data, and evaluation results.

- `dataset/`: Human annotation CSV files and inference/audit samples from sources such as Common Crawl, GitHub, Jira, and Stack Overflow.
- `eval/`: Evaluation data, scripts, and reports for RQ2.1.
- `scripts/`: Scripts for collecting or preparing samples from different sources.

### `rq2_2/`

Materials for RQ2.2 trend analysis.

- `scripts/`: Scripts for building four-month source trends and coverage trends.
- `results/`: Trend statistics for sources such as Jira, Stack Overflow, and GitHub, including CSV outputs and metadata files.

### `rq3/`

Materials for RQ3, including case data, RAG experiments, intermediate retrieval outputs, model outputs, and human/LLM evaluation files.

- `data/`: Original case datasets and experiment samples, covering sources such as BGL, HDFS, HPC, Proxifier, Spark, and Zookeeper.
- `scripts/`: Scripts for baseline runs, RAG runs, summarization, LLM judging, and API routing.
- `results/`: Final explanation outputs from the baseline and RAG settings.
- `retrieval_results/`: Intermediate RAG retrieval outputs, including queries, candidate documents, retrieval configurations, and retrieved document IDs.
- `summarizer_results/`: Summarizer outputs for each data source and case.
- `llm_judge/`: Aggregate LLM judge results and per-item judging trajectories.
- `human_review/`: Human review templates, instructions, and review notes for selected cases.
