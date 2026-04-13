# ArchLogicRAG: Early-stage architecture design assistance by LLMs and knowledge graphs

[![DOI](https://img.shields.io/badge/DOI-10.1016/j.autcon.2025.106756-darkgreen.svg)](https://doi.org/10.1016/j.autcon.2025.106756) [![License: GNU](https://img.shields.io/badge/License-GNU-red.svg)](https://www.gnu.org/licenses/) [![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/release/python-312/) [![uv Version](https://img.shields.io/badge/uv-0.8.19-purple.svg)](https://pypi.org/project/uv/) 

Official code repo for "Early-stage architecture design assistance by LLMs and knowledge graphs", accepted by Automation in Construction.

For coding agents and automation-specific repository guidance, see `AGENTS.md`.

For the full pipeline from scratch, see `docs/from-scratch.md`.

We have released the code and dataset. Here is the timeline for the remaining deliverables:

**Update plan**
- [x] Feb 2026: Upload dataset and source code for both terminal chatbot and web-based UI.
- [x] April 2026: Update dataset license.

## 1. Prerequisites

- Python 3.11+
- `uv` (recommended): https://docs.astral.sh/uv/getting-started/installation/

## 2. Clone and install

```bash
git clone https://github.com/danruili/ArchLogicRAG.git
cd ArchLogicRAG
uv sync
```

## 3. Prepare database files


### Option 1: Build from scratch

Please follow [Full pipeline guide](docs/from-scratch.md) using the original WikiArch dataset (see details in its [readme](docs/wikiarch_README.md)).

### Option 2: Download prebuilt data/index package

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

Notice: the prebuilt data/index package is NOT released under `CC0` license. It is under `CC BY-SA 4.0` license.

## 4. Configure environment keys

Copy and edit env values:

```bash
cp .env.example .env
```

Set:
- `OPENAI_API_KEY` (required for chatbot/extraction/indexing)
- `REPLICATE_API_TOKEN` (required for image retrieval/indexing features)

## 5. Run the terminal chatbot (optional)

```bash
uv run python -m src.agent.run_in_terminal
```

Optional:

```bash
uv run python -m src.agent.run_in_terminal --source-dir data/wikiarch --index-dir data/wikiarch/index --log-level INFO
```

## 6. Run the web app

```bash
uv run flask --app src.web.app:app run --host 0.0.0.0 --port 5000 --debug
```

Open:
- http://127.0.0.1:5000/


## License

This project contains multiple components with different licenses:


- **Code**: Released under the [GNU General Public License v3.0 (GPL-3.0)](https://www.gnu.org/licenses/gpl-3.0.en.html)  
- [**Original WikiArch Dataset**](data/wikiarch.json): Released under the [CC0 1.0 Universal (Public Domain Dedication)](https://creativecommons.org/publicdomain/zero/1.0/)  
- [**Prebuilt Data / Index Package**](https://drive.google.com/file/d/1vvENjnBZa49pvg2ZJhn8qoD1NC0nVkQ5/view?usp=sharing): Released under the [Creative Commons Attribution-ShareAlike 4.0 (CC BY-SA 4.0)](https://creativecommons.org/licenses/by-sa/4.0/)  

Please ensure compliance with the respective licenses when using or redistributing each component.


## Cite
```
@article{LI2026106756,
title = {Early-stage architecture design assistance by LLMs and knowledge graphs},
journal = {Automation in Construction},
volume = {182},
pages = {106756},
year = {2026},
issn = {0926-5805},
doi = {https://doi.org/10.1016/j.autcon.2025.106756},
url = {https://www.sciencedirect.com/science/article/pii/S0926580525007964},
author = {Danrui Li and Yichao Shi and Mathew Schwartz and Mubbasir Kapadia},
}
```