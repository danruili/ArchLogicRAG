"""
Design-logic extraction for one asset: image(s) or text.

Follows the old logic_extraction flow: image description → extraction → gleaning
→ (for images) augmentation with ref_text → reformat → archseek → (text-only) metadata.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.common.llm_client import chat, chat_and_parse_json_list, get_text_model, get_vision_model
from .prompts import PROMPTS

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
TEXT_EXTENSIONS = {".txt", ".md"}
SKIP_FILENAMES = {"link.txt"}


def _append_msg(messages: list[dict], role: str, content: str, image_paths: list[Path] | None = None) -> None:
    messages.append({"role": role, "content": content, **({"image_paths": image_paths} if image_paths else {})})


def asset_inquiry(
    text: str | None = None,
    img_paths: list[Path] | None = None,
    ref_text: str | None = None,
    max_gleaning: int = 1,
    model_vision: str | None = None,
    model_text: str | None = None,
) -> list[dict[str, Any]]:
    """
    Extract design logic from the given text and/or images.

    - If img_paths: describe image → extract logic → gleaning → augment with ref_text → reformat → archseek.
    - If text only: extract logic → gleaning → reformat → archseek → metadata.
    """
    model_v = model_vision or get_vision_model()
    model_t = model_text or get_text_model()
    messages: list[dict] = []
    img_desc: str | None = None
    augmented_img_desc: str | None = None

    if img_paths:
        _append_msg(messages, "user", PROMPTS["image_description"], image_paths=[Path(p) for p in img_paths])
        response = chat(messages, model=model_v)
        img_desc = response
        _append_msg(messages, "assistant", response)
        extraction_prompt = PROMPTS["asset_extraction"].replace(
            "{beginning}", PROMPTS["image_extraction_beginning"]
        )
    else:
        extraction_prompt = PROMPTS["asset_extraction"].replace(
            "{beginning}", PROMPTS["text_extraction_beginning"]
        )

    if text:
        extraction_prompt += f"\nText: {text}\n"

    _append_msg(messages, "user", extraction_prompt)
    json_dict, response = chat_and_parse_json_list(messages, model=model_v, verify_as_list=True)
    _append_msg(messages, "assistant", response)

    for obj in json_dict:
        obj["round"] = 1
    intermediate_result: list[dict] = list(json_dict)

    # Gleaning
    if len(intermediate_result) > 0:
        continue_prompt = PROMPTS["entiti_continue_extraction"]
        if_loop_prompt = PROMPTS["entiti_if_loop_extraction"]
        for i in range(max_gleaning):
            _append_msg(messages, "user", continue_prompt)
            json_dict, response = chat_and_parse_json_list(messages, model=model_v, verify_as_list=True)
            for obj in json_dict:
                obj["round"] = i + 2
            intermediate_result.extend(json_dict)
            _append_msg(messages, "assistant", response)
            _append_msg(messages, "user", if_loop_prompt)
            response = chat(messages, model=model_v)
            messages.pop()
            if "NO" in response.upper():
                break

    # Augmentation for images
    if img_paths:
        _append_msg(messages, "user", PROMPTS["augment_image_description"])
        response = chat(messages, model=model_v)
        augmented_img_desc = response
        messages.pop()

        if ref_text:
            _append_msg(messages, "user", PROMPTS["image_augment"].format(text=ref_text))
            json_dict, response = chat_and_parse_json_list(messages, model=model_v, verify_as_list=True)
            for obj in json_dict:
                obj["round"] = 99
            intermediate_result.extend(json_dict)
        else:
            logging.warning("ref_text is None, skipping image augmentation with text.")

    logging.info("Extracted %s design logics.", len(intermediate_result))

    # Reformat
    stringified = json.dumps(intermediate_result, ensure_ascii=False, indent=2)
    reformat_messages = [
        {"role": "system", "content": PROMPTS["reformat"]},
        {"role": "user", "content": f"```json\n{stringified}\n```"},
    ]
    json_dict, _ = chat_and_parse_json_list(reformat_messages, model=model_t, verify_as_list=True)
    logging.info("Reformatted %s design logics.", len(json_dict))

    if img_desc is not None:
        json_dict.append({"image_description": img_desc})
        json_dict.append({"augmented_image_description": augmented_img_desc})

    json_dict.append({
        "archseek": archseek_extraction(
            text=text, img_paths=img_paths, model_vision=model_v, model_text=model_t
        )
    })

    if img_paths is None and text:
        meta = metadata_extraction(text, model=model_t)
        if meta:
            json_dict.append({"metadata": meta})

    return json_dict


def metadata_extraction(text: str, model: str | None = None) -> dict[str, Any] | None:
    """Extract metadata (designer, year, country, etc.) from text."""
    model = model or get_text_model()
    messages = [
        {"role": "system", "content": PROMPTS["extract_metadata"]},
        {"role": "user", "content": text},
    ]
    try:
        parsed, _ = chat_and_parse_json_list(messages, model=model, verify_as_list=False)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def archseek_extraction(
    text: str | None = None,
    img_paths: list[Path] | None = None,
    model_vision: str | None = None,
    model_text: str | None = None,
) -> dict[str, Any]:
    """ArchSeek-style extraction: structured aspects (form, style, material, etc.)."""
    model_v = model_vision or get_vision_model()
    model_t = model_text or get_text_model()
    messages: list[dict] = []
    if img_paths:
        _append_msg(messages, "user", PROMPTS["archseek_extraction"], image_paths=[Path(p) for p in img_paths])
    else:
        _append_msg(messages, "user", PROMPTS["archseek_extraction"] + f"\nText: {text or ''}")
    json_dict, response = chat_and_parse_json_list(messages, model=model_v if img_paths else model_t, verify_as_list=False)
    archseek_dict = dict(json_dict) if isinstance(json_dict, dict) else {}
    _append_msg(messages, "assistant", response)

    # Gleaning for archseek
    _append_msg(messages, "user", PROMPTS["entiti_continue_extraction"])
    json_dict, response = chat_and_parse_json_list(messages, model=model_v if img_paths else model_t, verify_as_list=False)
    _append_msg(messages, "assistant", response)
    if isinstance(json_dict, dict):
        for topic, content in json_dict.items():
            if topic not in archseek_dict:
                archseek_dict[topic] = content
            else:
                existing = archseek_dict[topic]
                if isinstance(existing, list) and isinstance(content, list):
                    archseek_dict[topic] = existing + content
                else:
                    archseek_dict[topic] = content
    return archseek_dict


def extract_image(
    image_path: Path,
    project_name: str,
    ref_text: str | None = None,
    max_gleaning: int = 1,
) -> list[dict[str, Any]]:
    """
    Run design-logic extraction on one image (with optional ref_text for augmentation).

    Args:
        image_path: Path to the image.
        project_name: Name of the project (for logging).
        ref_text: Reference text (e.g. concatenated description.txt) to augment image logic.
        max_gleaning: Max extra gleaning rounds.

    Returns:
        List of dicts: strategy/goal logic, image_description, augmented_image_description, archseek.
    """
    result = asset_inquiry(
        img_paths=[Path(image_path)],
        ref_text=ref_text or "",
        max_gleaning=max_gleaning,
    )
    for r in result:
        r["asset_name"] = image_path.name
    return result


def extract_text(
    text_content: str,
    asset_name: str,
    max_gleaning: int = 1,
) -> list[dict[str, Any]]:
    """
    Run design-logic extraction on one text asset.

    Args:
        text_content: Raw text (e.g. from description.txt).
        asset_name: Filename or identifier for this asset.
        max_gleaning: Max extra gleaning rounds.

    Returns:
        List of dicts: strategy/goal logic, archseek, metadata.
    """
    result = asset_inquiry(text=text_content, max_gleaning=max_gleaning)
    for r in result:
        r["asset_name"] = asset_name
    return result


def yield_text_files(source_dir: Path):
    """Yield paths to .txt and .md files in source_dir, skipping link.txt."""
    for f in source_dir.iterdir():
        if not f.is_file():
            continue
        if f.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        if f.name in SKIP_FILENAMES or "link.txt" in f.name:
            continue
        yield f
