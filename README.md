# ArchLogicRAG

Official code repo for "Early-stage architecture design assistance by LLMs and knowledge graphs", accepted by Automation in Construction.

Thanks for visiting this repo, we are still organizing the code and files. Here is the timeline.

**Update plan**
- [x] Feb 2026: Upload dataset, processing scripts, and indexing scripts.
- [ ] Mar 2026: Upload source code for terminal chatbot agent.
- [ ] Apr 2026: Upload source code for user interface. Build demo web page.

## User instructions

For coding agents and automation-specific repository guidance, see `AGENTS.md`.

### A. Prerequisites

- **Python 3.11+**
- **uv** (recommended) — [install uv](https://docs.astral.sh/uv/getting-started/installation/). Alternatively use `pip` and a virtual environment.

### B. Setup

1. **Clone the repo**
   ```bash
   git clone https://github.com/danruili/ArchLogicRAG.git
   cd ArchLogicRAG
   ```

2. **Install dependencies** (with uv)
   ```bash
   uv sync
   ```
   Or with pip: `pip install -e .`

3. **Environment variables** (optional, for LLM and indexing)
   - Copy the example env file and edit as needed:
     ```bash
     cp .env.example .env
     ```
   - Set at least `OPENAI_API_KEY` when using extraction and text indexing.
   - Set `REPLICATE_API_TOKEN` when using image indexing.
   - Optional indexing vars:
     - `CHROMA_PERSIST_DIR`
     - `CHROMA_COLLECTION_NAME`
     - `OPENAI_EMBEDDING_MODEL`
     - `OPENAI_EMBEDDING_DIM`
     - `INDEX_EXTRACTION_DIR`
     - `INDEX_REFERENCE_DIR`
     - `INDEX_WORKSPACE_DIR`
     - `INDEX_ENABLE_CLUSTER`
     - `INDEX_SHOW_PROGRESS`
     - `INDEX_RAW_DIR`
     - `IMG_INDEX_OUTPUT_DIR`
     - `IMG_INDEX_MAX_WORKERS`
     - `IMG_INDEX_SHOW_PROGRESS`

### C. Downloading the WikiArch dataset

The script reads `wikiarch.json` and downloads images plus Wikipedia descriptions.

Writes to `data/wikiarch/raw/` (one subfolder per item, with images and `description.txt`).

```bash
uv run python -m src.pipeline.download_dataset
```

Use `--help` for full options.

### D. Extract Annotations

- **Extract all projects** (reads project folders from `data/wikiarch/raw` by default):
  ```bash
  uv run python -m src.pipeline.extraction.runner
  ```
  Output files are saved under `data/wikiarch/extraction/<project_name>.json`.

- **Extract one project** and save to `data/wikiarch/extraction/<project_name>.json`:
  ```bash
  uv run python -m src.pipeline.extraction.runner --project "111 Somerset" --force
  ```

Use `--help` for full options.

### E. Build and Query Text/Logic Index

Indexing entrypoint:

```bash
uv run python -m src.pipeline.indexing.runner
```

- Build index from extraction JSON files:
  ```bash
  uv run python -m src.pipeline.indexing.runner build --force
  ```
- Query indexed data:
  ```bash
  uv run python -m src.pipeline.indexing.runner query "daylight strategy with facade control" --top-k 5
  ```
- Show index metadata:
  ```bash
  uv run python -m src.pipeline.indexing.runner info
  ```

Default outputs:
- Chroma collection data: `data/wikiarch/index/chroma/`
- Reference maps: `data/wikiarch/index/reference/`
- Cluster artifacts: `data/wikiarch/index/cluster_matrix/`

### F. Build Image Embedding Index

Image indexing entrypoint:

```bash
uv run python -m src.pipeline.indexing.img_index
```

- Build image embedding index from `data/wikiarch/raw` using `data/wikiarch/index/reference/asset_id_map.json`:
  ```bash
  uv run python -m src.pipeline.indexing.img_index build
  ```
- Show image index metadata:
  ```bash
  uv run python -m src.pipeline.indexing.img_index info
  ```

Default outputs:
- Image embeddings: `data/wikiarch/index/img_index/embeddings.npy`
- Image records: `data/wikiarch/index/img_index/records.json`
- Metadata: `data/wikiarch/index/img_index/meta.json`
