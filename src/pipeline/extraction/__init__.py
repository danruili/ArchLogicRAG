"""
Design-logic extraction over wikiarch project folders (following old/ methods).

- asset_inquiry: one asset (image(s) or text) → design logic, archseek, metadata.
- Images: describe → extract → gleaning → augment with ref_text → reformat → archseek.
- Text: extract → gleaning → reformat → archseek → metadata.
- Runner walks project folders, runs image and text extraction in parallel, saves flat list.
"""

from __future__ import annotations

from .archseek_augment import add_for_one_case, add_for_all_cases
from .asset_inquiry import (
    IMAGE_EXTENSIONS,
    archseek_extraction,
    asset_inquiry,
    extract_image,
    extract_text,
    metadata_extraction,
    yield_text_files,
)
from src.common.llm_client import get_openai_client

__all__ = [
    "asset_inquiry",
    "archseek_extraction",
    "metadata_extraction",
    "add_for_one_case",
    "add_for_all_cases",
    "get_openai_client",
    "extract_image",
    "extract_text",
    "extract_project_folder",
    "extract_dataset",
    "resolve_project_root",
    "iter_project_folders",
    "resolve_project_dir",
    "IMAGE_EXTENSIONS",
    "yield_text_files",
]


def __getattr__(name: str):
    """Lazy-export runner helpers to avoid eager import side effects for `python -m`."""
    if name in {
        "extract_project_folder",
        "extract_dataset",
        "resolve_project_root",
        "iter_project_folders",
        "resolve_project_dir",
    }:
        from . import runner as _runner

        return getattr(_runner, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
