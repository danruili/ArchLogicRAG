"""
Augment existing extraction JSON with ArchSeek-derived logic.

Reads flat-list extractions (e.g. extractions.json), groups by asset_name, and for each
asset that has archseek runs an LLM to merge archseek summary into the existing logic list.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from tenacity import retry, stop_after_attempt, wait_fixed

from src.common.llm_client import chat_and_parse_json_list, get_text_model

AUGMENT_PROMPT = """
You are an expert in architecture design. You have been given a list of existing logic and a design summary. Your task is to augment the existing logic with the summary.
- Follow the existing logic format.
- Do not repeat the existing logic.
- Respond in JSON format.

## Guidelines for Extraction
1. **Strict Separation of Strategy and Goal**  
   - The **strategy** field must only describe **what is designed** (the physical or spatial decision).  
   - The **goal** field must describe **why it is designed that way** (the intended functional, social, environmental, or aesthetic impact).
   - Do not mix design intent into the **strategy** field. Any explanation of **ensuring, improving, enhancing, or facilitating** must be placed in the **goal** field.

2. If there are no design logics to be extracted, return an empty list in JSON format:
```json
[]
```

3. Don't refer to the design project name, instead, use "the building", instead of specific names or "museum", "library", etc.

## Existing Logic:
```json
{existing_logic}
```

## Design Summary:
```json
{design_summary}
```

"""


def _group_by_asset(data: list[dict]) -> dict[str, dict]:
    """Group flat list by asset_name; each group has 'logic' (list) and optionally 'archseek' (dict)."""
    grouped: dict[str, dict[str, Any]] = {}
    for item in data:
        asset_name = item.get("asset_name")
        if asset_name is None:
            continue
        if asset_name not in grouped:
            grouped[asset_name] = {}
        if "archseek" in item:
            grouped[asset_name]["archseek"] = item["archseek"]
        elif "strategy" in item and "goal" in item:
            grouped[asset_name].setdefault("logic", []).append({
                "strategy": item["strategy"],
                "goal": item["goal"],
            })
    return grouped


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def augment_logic(existing_logic: list[dict], archseek_result: dict, model: str | None = None) -> list[dict]:
    """Merge archseek design summary into existing strategy/goal logic via LLM."""
    model = model or get_text_model()
    prompt = AUGMENT_PROMPT.replace(
        "{existing_logic}", json.dumps(existing_logic, indent=2, ensure_ascii=False)
    ).replace(
        "{design_summary}", json.dumps(archseek_result, indent=2, ensure_ascii=False)
    )
    messages = [{"role": "user", "content": prompt}]
    parsed, _ = chat_and_parse_json_list(messages, model=model, verify_as_list=True)
    return parsed


def add_for_one_case(json_file_path: Path, model: str | None = None) -> None:
    """
    Read extraction JSON (flat list), augment each asset's logic with its archseek result, append new logic, save.
    """
    json_file_path = Path(json_file_path)
    if not json_file_path.exists():
        raise FileNotFoundError(f"File not found: {json_file_path}")
    with open(json_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("JSON must be a list of items")

    grouped = _group_by_asset(data)
    all_new: list[dict] = []
    for asset_name, asset_data in grouped.items():
        if "archseek" not in asset_data:
            continue
        existing_logic = asset_data.get("logic", [])
        augmented = augment_logic(existing_logic, asset_data["archseek"], model=model)
        for logic in augmented:
            logic["asset_name"] = asset_name
            logic["source"] = "archseek"
            logic["round"] = 1
        all_new.extend(augmented)

    data.extend(all_new)
    with open(json_file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def add_for_all_cases(
    working_dir: Path,
    *,
    output_filename: str = "extractions.json",
    model: str | None = None,
    max_workers: int = 5,
) -> None:
    """
    Run add_for_one_case on each extraction JSON.

    - If working_dir contains .json files directly (flat list): process each .json file.
    - Else: treat as wikiarch root; for each subdir that has output_filename, process it.
    """
    working_dir = Path(working_dir).resolve()
    json_files = [p for p in working_dir.iterdir() if p.is_file() and p.suffix.lower() == ".json"]
    if json_files:
        paths = json_files
    else:
        paths = [p / output_filename for p in working_dir.iterdir() if p.is_dir() and (p / output_filename).exists()]
    if not paths:
        logging.warning("No JSON / %s files found under %s", output_filename, working_dir)
        return
    from concurrent import futures
    with futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        fs = {executor.submit(add_for_one_case, p, model): p for p in paths}
        for future in futures.as_completed(fs):
            try:
                future.result()
            except Exception as e:
                logging.error("Error processing %s: %s", fs[future], e)
