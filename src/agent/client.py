"""Shared LLM client access for agent modules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.common.llm_client import (
    chat as _chat,
    chat_and_parse_json_list,
    get_openai_client,
    get_text_model,
    get_vision_model,
)


@dataclass(slots=True)
class Message:
    role: str
    content: str


class ChatSequence(list[Message]):
    pass


class LLMHandler:
    def chat(self, payload, model: str | None = None) -> str:
        model = model or get_text_model()
        if isinstance(payload, str):
            messages = [{"role": "user", "content": payload}]
            return _chat(messages=messages, model=model)

        messages = []
        if isinstance(payload, Iterable):
            for item in payload:
                if isinstance(item, Message):
                    messages.append({"role": item.role, "content": item.content})
                elif isinstance(item, dict):
                    messages.append({"role": item["role"], "content": item["content"]})
        return _chat(messages=messages, model=model)


__all__ = [
    "get_openai_client",
    "get_vision_model",
    "get_text_model",
    "chat_and_parse_json_list",
    "LLMHandler",
    "ChatSequence",
    "Message",
]
