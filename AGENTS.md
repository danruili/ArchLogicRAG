# AGENTS.md

Guidance for coding agents working in this repository.

## Purpose

ArchLogicRAG supports early-stage architectural design analysis with LLM/VLM extraction over WikiArch-style assets.

Primary implemented workflows in this repo:
- Dataset download from `data/wikiarch.json`
- Project-level extraction from images + text assets

## Repository Map

- `src/pipeline/download_dataset.py`
  - Downloads image assets and Wikipedia descriptions.
  - Default output: `data/wikiarch/raw/`
- `src/common/llm_client.py`
  - Shared OpenAI client/model helpers used by both pipeline and agent modules.
- `src/pipeline/extraction/`
  - `runner.py`: unified extraction CLI (all projects or one project)
  - `asset_inquiry.py`: core extraction orchestration
  - `image_extractor.py`: image asset extraction
  - `text_extractor.py`: text asset extraction
  - `archseek_augment.py`: post-process ArchSeek augmentation
  - `prompts.py`: prompt templates
  - `client.py`: compatibility shim re-exporting `src.common.llm_client`
- `data/wikiarch/`
  - `raw/`: one folder per project with images + `description.txt`
  - `extraction/`: one JSON per project when running one-project mode

## Current Data Layout Contract

- Input project folders are expected under:
  - `data/wikiarch/raw/<project_name>/`
- Per-project extraction output (one-project mode):
  - `data/wikiarch/extraction/<project_name>.json`
- All-project mode default output:
  - `data/wikiarch/extraction/<project_name>.json`

## Extraction CLI

Main entrypoint:
- `uv run python -m src.pipeline.extraction.runner`

Modes:
- All projects:
  - `uv run python -m src.pipeline.extraction.runner`
- One project:
  - `uv run python -m src.pipeline.extraction.runner --project "Vyborg Library" --force`

Path resolution behavior for positional `wikiarch_path`:
- If path contains `raw/`, it is treated as wikiarch root.
- If path itself is `.../raw`, it is treated as project root.
- Otherwise it is treated as project root directly.

## Download CLI

- Default:
  - `uv run python -m src.pipeline.download_dataset`
- Explicit:
  - `uv run python -m src.pipeline.download_dataset data/wikiarch.json data/wikiarch/raw`

Important flags:
- `--limit`
- `--force`
- `--dry-run`
- `--thumbnail`
- `--delay` (must be >= 1.0 seconds per Wikimedia policy)

## Environment and Dependencies

- Python: `>=3.11`
- Install:
  - `uv sync`
- Required for extraction:
  - `OPENAI_API_KEY` in `.env`
- Notable dependencies:
  - `openai`, `tenacity`, `requests`, `beautifulsoup4`, `pillow`, `wikipedia-api`

## Coding Conventions for This Repo

- Keep extraction logic centralized in `src/pipeline/extraction/runner.py`.
- Avoid duplicate CLI flows for one-project vs all-project extraction.
- Prefer reusing existing helpers in `runner.py` for path and project resolution.
- Preserve current data layout (`data/wikiarch/raw`, `data/wikiarch/extraction`) unless explicitly requested.
- Do not reintroduce deprecated alias exports unless needed for compatibility.

## Validation Checklist After Changes

- Search for stale paths:
  - `data/wikiarch/` assumptions that should be `data/wikiarch/raw/`
- Confirm docs and CLI examples match actual defaults.
- Run tests:
  - `uv run pytest`
- Sanity-check CLI help:
  - `uv run python -m src.pipeline.extraction.runner --help`
  - `uv run python -m src.pipeline.download_dataset --help`
