# ArchLogicRAG

Official code repo for "Early-stage architecture design assistance by LLMs and knowledge graphs", accepted by Automation in Construction.

Thanks for visiting this repo, we are still organizing the code and files. Here is the timeline.

**Update plan**
- [x] Feb 2026: Upload dataset and processing scripts.
- [ ] Mar 2026: Upload source code for key components
- [ ] Apr 2026: Upload source code for user interface. Build demo web page.



## User instructions

For coding agents and automation-specific repository guidance, see `AGENTS.md`.

### Prerequisites

- **Python 3.11+**
- **uv** (recommended) — [install uv](https://docs.astral.sh/uv/getting-started/installation/). Alternatively use `pip` and a virtual environment.

### Setup

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

3. **Environment variables** (optional, for LLM and Chroma)
   - Copy the example env file and edit as needed:
     ```bash
     cp .env.example .env
     ```
   - Set at least `OPENAI_API_KEY` when using the indexing pipeline or agent. Adjust `CHROMA_PERSIST_DIR` and `CHROMA_COLLECTION_NAME` if you change where the vector store lives.

### Downloading the WikiArch dataset

The script reads `wikiarch.json` and downloads images plus Wikipedia descriptions. 

Writes to `data/wikiarch/raw/` (one subfolder per item, with images and `description.txt`).

  ```bash
  uv run python -m src.pipeline.download_dataset
  ```

Use `--help` for full options.

### Extract Annotations

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

