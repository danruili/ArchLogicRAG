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

### G. Run the Terminal Chatbot

Start the chatbot in terminal mode:

```bash
uv run python -m src.agent.run_in_terminal
```

Optional arguments:
- `--source-dir` (default: `data/wikiarch`)
- `--index-dir` (default: `data/wikiarch/index`)
- `--log-level` (`DEBUG`, `INFO`, `WARNING`, `ERROR`; default: `INFO`)

Example:

```bash
uv run python -m src.agent.run_in_terminal --source-dir data/wikiarch --index-dir data/wikiarch/index --log-level INFO
```

Notes:
- Build the text/logic index before running terminal chat (`src.pipeline.indexing.runner build`), or retrieval will fail on an empty Chroma index.
- The chatbot will exit when you type `bye`, `exit`, or `quit`.

### H. Run the Web Server

Start the Flask web server:

```bash
uv run flask --app src.web.app:app run --host 0.0.0.0 --port 5000 --debug
```

Then open:
- `http://127.0.0.1:5000/`
- or `http://127.0.0.1:5000/chat/`

Notes:
- The web app expects source data under `data/wikiarch` (or `data/wikiarch/raw` for image assets).
- The conversation endpoint uses the same chatbot backend as terminal mode, so ensure:
  - `OPENAI_API_KEY` and `REPLICATE_API_TOKEN` are set for LLM and image retrieval.
  - text/logic index is built at `data/wikiarch/index` (or configure equivalent paths)
