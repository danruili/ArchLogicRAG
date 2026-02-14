"""
Shared OpenAI client helpers for agent and pipeline modules.

Uses OPENAI_API_KEY from environment. Configure model names via env:
- OPENAI_VISION_MODEL
- OPENAI_TEXT_MODEL
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from tenacity import retry, stop_after_attempt, wait_fixed

_client: object | None = None
_env_loaded = False


def _load_project_env_once() -> None:
    """Best-effort load of <repo_root>/.env without overriding existing env vars."""
    global _env_loaded
    if _env_loaded:
        return
    _env_loaded = True

    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value


def get_openai_client():
    """Return OpenAI client; requires openai package and OPENAI_API_KEY."""
    global _client
    _load_project_env_once()
    if _client is None:
        try:
            from openai import OpenAI
        except ImportError as e:
            raise ImportError("Install openai: uv add openai (or pip install openai)") from e
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError("OPENAI_API_KEY must be set")
        _client = OpenAI(api_key=key)
    return _client


def get_vision_model() -> str:
    """Model used for image (VLM) extraction."""
    _load_project_env_once()
    return os.environ.get("OPENAI_VISION_MODEL", "gpt-4o")


def get_text_model() -> str:
    """Model used for text extraction."""
    _load_project_env_once()
    return os.environ.get("OPENAI_TEXT_MODEL", "gpt-4o")


def _mime_for_path(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in (".jpg", ".jpeg"):
        return "image/jpeg"
    if ext == ".png":
        return "image/png"
    if ext in (".gif", ".webp"):
        return f"image/{ext.lstrip('.')}"
    return "image/jpeg"


def _encode_image(path: Path) -> str:
    with open(path, "rb") as f:
        b64 = __import__("base64").standard_b64encode(f.read()).decode("ascii")
    mime = _mime_for_path(path)
    return f"data:{mime};base64,{b64}"


def _message_to_openai(role: str, content: str, image_paths: list[Path] | None = None) -> dict:
    if not image_paths:
        return {"role": role, "content": content}
    parts = [{"type": "text", "text": content}]
    for p in image_paths:
        url = _encode_image(p)
        parts.append({"type": "image_url", "image_url": {"url": url}})
    return {"role": role, "content": parts}


def chat(messages: list[dict], model: str | None = None) -> str:
    """
    Send a chat completion. messages: list of {role, content, image_paths?}.
    Returns assistant content string.
    """
    client = get_openai_client()
    model = model or get_vision_model()
    openai_messages = []
    for m in messages:
        role = m["role"]
        content = m["content"]
        image_paths = m.get("image_paths")
        if isinstance(image_paths, list):
            image_paths = [Path(x) for x in image_paths]
        openai_messages.append(_message_to_openai(role, content, image_paths))
    resp = client.chat.completions.create(
        model=model,
        messages=openai_messages,
        max_tokens=4096,
    )
    return (resp.choices[0].message.content or "").strip()


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def chat_and_parse_json_list(
    messages: list[dict],
    model: str | None = None,
    verify_as_list: bool = True,
) -> tuple[Any, str]:
    """
    Call the model with the given message sequence, then parse a ```json ... ``` block.
    Returns (parsed_json, raw_response). Raises on parse failure (retried).
    """
    response = chat(messages, model=model)
    if response.strip() == "{}":
        return {}, response
    match = re.findall(r"```json\s*(.*?)\s*```", response, re.DOTALL)
    if not match:
        raise ValueError(f"No ```json``` block in response: {response[:200]}...")
    json_text = match[-1].strip()
    parsed = json.loads(json_text)
    if verify_as_list and not isinstance(parsed, list):
        raise ValueError("The response is not a valid JSON list.")
    return parsed, response
