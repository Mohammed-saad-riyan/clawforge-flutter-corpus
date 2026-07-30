# ClawForge Flutter Corpus

This repository stores a curated Flutter code corpus for ClawForge.

## Layout

- `raw/` — untouched repository snapshots and source mirrors.
- `curated/` — high-signal reusable slices grouped by pattern.
- `prs/` — pull request diffs, metadata, and review signals.
- `branches/` — branch metadata and commit sequences.
- `chunks/` — AST, symbol, and file-section chunks for retrieval.
- `embeddings/` — vector indexes or embedding exports.
- `eval/` — benchmarks, compile results, and scoring.
- `sources/` — source manifests and quality rubric.
- `scripts/` — ingestion and scoring utilities.

## Source policy

Prefer production-style Flutter repositories, templates, PRs, issues, and discussions that expose real implementation patterns for:

- Riverpod
- GoRouter
- Clean Architecture
- MVVM
- Authentication
- Forms
- Networking
- Persistence
- Testing
- Responsive UI

## Storage policy

1. Keep exact source snapshots under `raw/`.
2. Promote only the best reusable code into `curated/`.
3. Store PR diffs and review signals separately under `prs/`.
4. Store benchmark and analyzer outputs under `eval/`.

## Current status

This repo has been initialized as the corpus container for ClawForge. The next step is to ingest source repositories and populate manifests and curated slices.
