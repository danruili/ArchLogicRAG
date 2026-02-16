# ArchLogicRAG: Early-stage architecture design assistance by LLMs and knowledge graphs

[![DOI](https://img.shields.io/badge/DOI-10.1016/j.autcon.2025.106756-darkgreen.svg)](https://doi.org/10.1016/j.autcon.2025.106756) [![License: GNU](https://img.shields.io/badge/License-GNU-red.svg)](https://www.gnu.org/licenses/) [![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/release/python-312/) [![uv Version](https://img.shields.io/badge/uv-0.8.19-purple.svg)](https://pypi.org/project/uv/) 

Official code repo for "Early-stage architecture design assistance by LLMs and knowledge graphs", accepted by Automation in Construction.

For coding agents and automation-specific repository guidance, see `AGENTS.md`.

For the full pipeline from scratch, see `docs/from-scratch.md`.

We have released the code and dataset. Here is the timeline for the remaining deliverables:

**Update plan**
- [x] Feb 2026: Upload dataset and source code for both terminal chatbot and web-based UI.
- [ ] Mar 2026: Build demo web page.

## 1) Prerequisites

- Python 3.11+
- `uv` (recommended): https://docs.astral.sh/uv/getting-started/installation/

## 2) Clone and install

```bash
git clone https://github.com/danruili/ArchLogicRAG.git
cd ArchLogicRAG
uv sync
```

## 3) Download prebuilt data/index package

Download:
- https://drive.google.com/file/d/1vvENjnBZa49pvg2ZJhn8qoD1NC0nVkQ5/view?usp=sharing

Extract the downloaded files so your layout is:

```text
data/
└── wikiarch/
    ├── extraction/
    ├── index/
    └── raw/
```

After this, you can skip steps C, D, E, and F from the full pipeline guide.

## 4) Configure environment keys

Copy and edit env values:

```bash
cp .env.example .env
```

Set:
- `OPENAI_API_KEY` (required for chatbot/extraction/indexing)
- `REPLICATE_API_TOKEN` (required for image retrieval/indexing features)

## 5) Run the terminal chatbot

```bash
uv run python -m src.agent.run_in_terminal
```

Optional:

```bash
uv run python -m src.agent.run_in_terminal --source-dir data/wikiarch --index-dir data/wikiarch/index --log-level INFO
```

## 6) Run the web app

```bash
uv run flask --app src.web.app:app run --host 0.0.0.0 --port 5000 --debug
```

Open:
- http://127.0.0.1:5000/
