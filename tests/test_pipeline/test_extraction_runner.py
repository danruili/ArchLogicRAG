from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from src.pipeline.extraction import runner


def test_resolve_wikiarch_paths_variants(tmp_path: Path) -> None:
    wikiarch_root = tmp_path / "wikiarch"
    raw_dir = wikiarch_root / "raw"
    raw_dir.mkdir(parents=True)

    root_a, project_root_a = runner.resolve_wikiarch_paths(wikiarch_root)
    assert root_a == wikiarch_root.resolve()
    assert project_root_a == raw_dir.resolve()

    root_b, project_root_b = runner.resolve_wikiarch_paths(raw_dir)
    assert root_b == wikiarch_root.resolve()
    assert project_root_b == raw_dir.resolve()

    custom_root = tmp_path / "custom_projects"
    custom_root.mkdir()
    root_c, project_root_c = runner.resolve_wikiarch_paths(custom_root)
    assert root_c == custom_root.resolve()
    assert project_root_c == custom_root.resolve()


def test_resolve_project_dir_exact_and_case_insensitive(tmp_path: Path) -> None:
    project_root = tmp_path / "raw"
    project_root.mkdir()
    project_dir = project_root / "Vyborg Library"
    project_dir.mkdir()

    found_exact, name_exact = runner.resolve_project_dir(project_root, "Vyborg Library")
    assert found_exact == project_dir
    assert name_exact == "Vyborg Library"

    found_ci, name_ci = runner.resolve_project_dir(project_root, "vyborg library")
    assert found_ci == project_dir
    assert name_ci.lower() == "vyborg library"

    with pytest.raises(FileNotFoundError):
        runner.resolve_project_dir(project_root, "Missing Project")


def test_extract_project_folder_adds_raw_description_and_writes_output(
    monkeypatch, tmp_path: Path
) -> None:
    project_dir = tmp_path / "raw" / "111 Somerset"
    project_dir.mkdir(parents=True)
    (project_dir / "description.txt").write_text("Desc content", encoding="utf-8")
    (project_dir / "notes.md").write_text("Some notes", encoding="utf-8")
    (project_dir / "image.jpg").write_bytes(b"fake")
    output_path = tmp_path / "wikiarch" / "extraction" / "111 Somerset.json"

    def fake_extract_image(*args, **kwargs):
        return [{"strategy": "image strategy", "goal": "image goal", "asset_name": "image.jpg"}]

    def fake_extract_text(content: str, asset_name: str, max_gleaning: int = 1):
        return [{"strategy": "text strategy", "goal": "text goal", "asset_name": asset_name}]

    monkeypatch.setattr(runner, "extract_image", fake_extract_image)
    monkeypatch.setattr(runner, "extract_text", fake_extract_text)

    result = runner.extract_project_folder(
        project_dir=project_dir,
        project_name="111 Somerset",
        skip_existing=False,
        output_path=output_path,
        max_workers=1,
    )

    assert any(
        item.get("asset_name") == "description.txt" and item.get("raw_text") == "Desc content"
        for item in result
    )
    assert output_path.exists()
    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert persisted == result


def test_extract_dataset_and_project_mode_use_centralized_output_paths(
    monkeypatch, tmp_path: Path
) -> None:
    wikiarch_root = tmp_path / "wikiarch"
    raw_dir = wikiarch_root / "raw"
    (raw_dir / "ProjA").mkdir(parents=True)
    (raw_dir / "ProjB").mkdir(parents=True)

    calls: list[tuple[str, Path]] = []

    def fake_extract_project_folder(project_dir: Path, project_name: str, **kwargs):
        calls.append((project_name, kwargs["output_path"]))
        return [{"asset_name": "x"}]

    monkeypatch.setattr(runner, "extract_project_folder", fake_extract_project_folder)

    runner.extract_dataset(wikiarch_root, skip_existing=True)
    assert ("ProjA", wikiarch_root / "extraction" / "ProjA.json") in calls
    assert ("ProjB", wikiarch_root / "extraction" / "ProjB.json") in calls

    calls.clear()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "runner.py",
            str(wikiarch_root),
            "--project",
            "ProjA",
        ],
    )
    runner.main()
    assert calls == [("ProjA", wikiarch_root / "extraction" / "ProjA.json")]


def test_extract_project_folder_skip_existing_short_circuits(monkeypatch, tmp_path: Path) -> None:
    project_dir = tmp_path / "raw" / "ProjA"
    project_dir.mkdir(parents=True)
    output_path = tmp_path / "wikiarch" / "extraction" / "ProjA.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps([{"asset_name": "cached"}]), encoding="utf-8")

    def _should_not_be_called(*args, **kwargs):
        raise AssertionError("extractors should not be called when skip_existing=True and output exists")

    monkeypatch.setattr(runner, "extract_image", _should_not_be_called)
    monkeypatch.setattr(runner, "extract_text", _should_not_be_called)

    result = runner.extract_project_folder(
        project_dir=project_dir,
        project_name="ProjA",
        skip_existing=True,
        output_path=output_path,
    )
    assert result == [{"asset_name": "cached"}]
