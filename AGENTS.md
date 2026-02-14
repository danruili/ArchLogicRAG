# AGENTS.md

Guidance for coding agents working in this repository.

## Purpose

ArchLogicRAG supports early-stage architectural design analysis with LLM/VLM extraction over WikiArch-style assets.

Primary implemented workflows in this repo:
- Dataset download from `data/wikiarch.json`
- Project-level extraction from images + text assets
- Design-logic indexing into ChromaDB from extraction outputs
- Image embedding indexing over raw project images

## Repository Map

- `src/pipeline/download_dataset.py`
  - Downloads image assets and Wikipedia descriptions.
  - Default output: `data/wikiarch/raw/`
- `src/common/llm_client.py`
  - Shared OpenAI client/model helpers used by both pipeline and agent modules.
  - `_load_project_env_once()` loads `.env` values before runtime config reads.
- `src/common/replicate_api.py`
  - Image/text embedding helpers backed by Replicate.
  - Used by image indexing for batched image embeddings.
- `src/pipeline/extraction/`
  - `runner.py`: unified extraction CLI (all projects or one project)
  - `asset_inquiry.py`: core extraction orchestration
  - `image_extractor.py`: image asset extraction
  - `text_extractor.py`: text asset extraction
  - `archseek_augment.py`: post-process ArchSeek augmentation
  - `prompts.py`: prompt templates
  - `client.py`: compatibility shim re-exporting `src.common.llm_client`
- `src/pipeline/indexing/`
  - `runner.py`: text/logic indexing CLI (`build`, `query`, `info`)
  - `chroma_index.py`: index config + ChromaDB lifecycle + query API
  - `img_index.py`: image indexing CLI (`build`, `info`) + image index build logic
  - `ingestion_parser.py`: logic-node parser transform over extraction JSON
  - `cluster_build.py`: optional hierarchical cluster/summarization transform
  - `cluster_utils.py`: clustering and summarization helpers
- `src/pipeline/indexing/reference/`
  - Legacy indexing prototype kept for reference; do not treat as primary entrypoint.
- `data/wikiarch/`
  - `raw/`: one folder per project with images + `description.txt`
  - `extraction/`: one JSON per project from extraction pipeline
  - `index/chroma/`: Chroma persisted collection data
  - `index/reference/`: `case_id_map.json` and `asset_id_map.json`
  - `index/cluster_matrix/`: clustering matrix artifacts when cluster stage is enabled
  - `index/img_index/`: image embedding index artifacts (`embeddings.npy`, `records.json`, `meta.json`)

## Current Data Layout Contract

- Input project folders are expected under:
  - `data/wikiarch/raw/<project_name>/`
- Per-project extraction output (one-project mode):
  - `data/wikiarch/extraction/<project_name>.json`
- All-project mode extraction output:
  - `data/wikiarch/extraction/<project_name>.json`
- Text/logic indexing outputs:
  - Chroma persistence: `data/wikiarch/index/chroma/`
  - Reference maps: `data/wikiarch/index/reference/`
  - Cluster artifacts: `data/wikiarch/index/cluster_matrix/`
- Image indexing outputs:
  - Embeddings: `data/wikiarch/index/img_index/embeddings.npy`
  - Records: `data/wikiarch/index/img_index/records.json`
  - Metadata: `data/wikiarch/index/img_index/meta.json`

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

## Text/Logic Indexing CLI

Main entrypoint:
- `uv run python -m src.pipeline.indexing.runner`

Commands:
- Build Chroma index:
  - `uv run python -m src.pipeline.indexing.runner build --force`
- Build without clustering/summarization transform:
  - `uv run python -m src.pipeline.indexing.runner build --no-cluster`
- Query index:
  - `uv run python -m src.pipeline.indexing.runner query "daylight strategy with facade control" --top-k 5`
- Index info:
  - `uv run python -m src.pipeline.indexing.runner info`

Notes:
- `.env` is loaded before indexing config resolution via `_load_project_env_once()`.
- Query embedding dimensions must match the collection embedding dimension.

## Image Indexing CLI

Main entrypoint:
- `uv run python -m src.pipeline.indexing.img_index`

Commands:
- Build image embedding index:
  - `uv run python -m src.pipeline.indexing.img_index build`
- Build with overwrite:
  - `uv run python -m src.pipeline.indexing.img_index build --force`
- Image index info:
  - `uv run python -m src.pipeline.indexing.img_index info`

Defaults:
- Raw image root: `data/wikiarch/raw/`
- Asset map input: `data/wikiarch/index/reference/asset_id_map.json`
- Output root: `data/wikiarch/index/img_index/`

Requirements:
- `REPLICATE_API_TOKEN` must be set in `.env`.

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
- Required for extraction and text indexing:
  - `OPENAI_API_KEY` in `.env`
- Required for image indexing:
  - `REPLICATE_API_TOKEN` in `.env`
- Notable dependencies:
  - `openai`, `tenacity`, `requests`, `beautifulsoup4`, `pillow`, `wikipedia-api`, `chromadb`, `llama-index`, `llama-index-vector-stores-chroma`, `scikit-learn`, `umap-learn`, `replicate`, `tqdm`

## Coding Conventions for This Repo

- Keep extraction logic centralized in `src/pipeline/extraction/runner.py`.
- Keep text indexing orchestration centralized in `src/pipeline/indexing/chroma_index.py` and CLI wiring in `src/pipeline/indexing/runner.py`.
- Keep image indexing orchestration centralized in `src/pipeline/indexing/img_index.py`.
- Avoid duplicate CLI flows for one-project vs all-project extraction.
- Prefer reusing existing helpers in `runner.py` modules for path/config resolution.
- Preserve current data layout (`data/wikiarch/raw`, `data/wikiarch/extraction`, `data/wikiarch/index`) unless explicitly requested.
- Do not reintroduce deprecated alias exports unless needed for compatibility.

## Validation Checklist After Changes

- Search for stale paths:
  - `data/wikiarch/` assumptions that should be `data/wikiarch/raw/`, `data/wikiarch/extraction/`, or `data/wikiarch/index/`
- Confirm docs and CLI examples match actual defaults.
- Run tests:
  - `uv run pytest`
- Sanity-check CLI help:
  - `uv run python -m src.pipeline.extraction.runner --help`
  - `uv run python -m src.pipeline.download_dataset --help`
  - `uv run python -m src.pipeline.indexing.runner --help`
  - `uv run python -m src.pipeline.indexing.img_index --help`
- Optional indexing smoke checks:
  - `uv run python -m src.pipeline.indexing.runner info`
  - `uv run python -m src.pipeline.indexing.img_index info`
