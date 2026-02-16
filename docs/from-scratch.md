# ArchLogicRAG: Full Pipeline (From Scratch)

This guide covers the complete workflow, including dataset download and rebuilding both text and image indexes.

## A. Prerequisites

- Python 3.11+
- `uv` (recommended) - https://docs.astral.sh/uv/getting-started/installation/

## B. Setup

1. Clone the repo

```bash
git clone https://github.com/danruili/ArchLogicRAG.git
cd ArchLogicRAG
```

2. Install dependencies

```bash
uv sync
```

3. Configure environment variables

```bash
cp .env.example .env
```

Set:
- `OPENAI_API_KEY` for extraction and text indexing
- `REPLICATE_API_TOKEN` for image indexing

## C. Download the WikiArch dataset

Default:

```bash
uv run python -m src.pipeline.download_dataset
```

Explicit:

```bash
uv run python -m src.pipeline.download_dataset data/wikiarch.json data/wikiarch/raw
```

Use `--help` for options such as `--limit`, `--force`, `--dry-run`, `--thumbnail`, and `--delay`.

## D. Extract annotations

Extract all projects:

```bash
uv run python -m src.pipeline.extraction.runner
```

Extract one project:

```bash
uv run python -m src.pipeline.extraction.runner --project "111 Somerset" --force
```

Outputs are written to `data/wikiarch/extraction/<project_name>.json`.

## E. Build and query text/logic index

Build:

```bash
uv run python -m src.pipeline.indexing.runner build --force
```
It takes about 20 minutes and 3 USD to build the index for all 70 wikiarch projects.

Query:

```bash
uv run python -m src.pipeline.indexing.runner query "daylight strategy with facade control" --top-k 5
```

Info:

```bash
uv run python -m src.pipeline.indexing.runner info
```

## F. Build image embedding index

Build:

```bash
uv run python -m src.pipeline.indexing.img_index build
```
It takes about 5 minutes and 0.2 USD to build the index for all 70 wikiarch projects.

Overwrite existing index:

```bash
uv run python -m src.pipeline.indexing.img_index build --force
```

Info:

```bash
uv run python -m src.pipeline.indexing.img_index info
```

## G. Run the terminal chatbot

```bash
uv run python -m src.agent.run_in_terminal
```

Optional:

```bash
uv run python -m src.agent.run_in_terminal --source-dir data/wikiarch --index-dir data/wikiarch/index --log-level INFO
```

## H. Run the web server

```bash
uv run flask --app src.web.app:app run --host 0.0.0.0 --port 5000 --debug
```

Open:
- http://127.0.0.1:5000/
