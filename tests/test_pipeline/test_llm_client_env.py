from __future__ import annotations

import os
from pathlib import Path

from src.common import llm_client


def _point_module_to_repo(monkeypatch, repo_root: Path) -> None:
    fake_file = repo_root / "src" / "common" / "llm_client.py"
    fake_file.parent.mkdir(parents=True, exist_ok=True)
    if not fake_file.exists():
        fake_file.write_text("# test stub\n", encoding="utf-8")
    monkeypatch.setattr(llm_client, "__file__", str(fake_file))


def test_loads_project_env_when_missing(monkeypatch, tmp_path: Path) -> None:
    _point_module_to_repo(monkeypatch, tmp_path)
    (tmp_path / ".env").write_text(
        "OPENAI_TEXT_MODEL=gpt-test-text\nOPENAI_VISION_MODEL=gpt-test-vision\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENAI_TEXT_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_VISION_MODEL", raising=False)
    llm_client._env_loaded = False

    llm_client._load_project_env_once()

    assert os.environ["OPENAI_TEXT_MODEL"] == "gpt-test-text"
    assert os.environ["OPENAI_VISION_MODEL"] == "gpt-test-vision"


def test_does_not_overwrite_existing_and_handles_export_and_quotes(monkeypatch, tmp_path: Path) -> None:
    _point_module_to_repo(monkeypatch, tmp_path)
    (tmp_path / ".env").write_text(
        'export OPENAI_TEXT_MODEL="from-dotenv"\nOPENAI_VISION_MODEL=\'vision-dotenv\'\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "already-set")
    monkeypatch.delenv("OPENAI_VISION_MODEL", raising=False)
    llm_client._env_loaded = False

    llm_client._load_project_env_once()

    assert os.environ["OPENAI_TEXT_MODEL"] == "already-set"
    assert os.environ["OPENAI_VISION_MODEL"] == "vision-dotenv"


def test_missing_dotenv_is_noop(monkeypatch, tmp_path: Path) -> None:
    _point_module_to_repo(monkeypatch, tmp_path)
    monkeypatch.delenv("OPENAI_TEXT_MODEL", raising=False)
    llm_client._env_loaded = False

    llm_client._load_project_env_once()

    assert "OPENAI_TEXT_MODEL" not in os.environ

