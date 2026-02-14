"""
Walk data/wikiarch/raw project folders and run design-logic extraction per project.

Follows the old extract_for_one_case / extract_for_all_cases flow: for each project,
gather all text, then process each image (with ref_text=all_text) and each text file
in parallel; merge into a flat list and save.
"""

from __future__ import annotations

import json
from concurrent import futures
from pathlib import Path
from typing import Any

from .asset_inquiry import IMAGE_EXTENSIONS, extract_image, extract_text, yield_text_files


def resolve_wikiarch_paths(wikiarch_path: Path) -> tuple[Path, Path]:
    """
    Resolve wikiarch root and project-folder root.

    Accepts either:
    - wikiarch root (containing raw/)
    - raw folder itself
    - a direct project-folder root
    """
    wikiarch_path = Path(wikiarch_path).resolve()
    raw_dir = wikiarch_path / "raw"
    if raw_dir.is_dir():
        return wikiarch_path, raw_dir
    if wikiarch_path.name.lower() == "raw":
        return wikiarch_path.parent, wikiarch_path
    return wikiarch_path, wikiarch_path


def resolve_project_root(wikiarch_path: Path) -> Path:
    """Accept wikiarch root or raw dir; return project-folder root."""
    _, project_root = resolve_wikiarch_paths(wikiarch_path)
    return project_root


def iter_project_folders(wikiarch_root: Path):
    """Yield (project_dir, project_name) for each subdirectory that looks like a project."""
    if not wikiarch_root.is_dir():
        return
    for path in sorted(wikiarch_root.iterdir()):
        if path.is_dir() and not path.name.startswith("."):
            yield path, path.name


def resolve_project_dir(wikiarch_root: Path, project: str) -> tuple[Path, str]:
    """Resolve one project folder by exact name, then case-insensitive match."""
    direct = wikiarch_root / project
    if direct.is_dir():
        return direct, direct.name

    needle = project.strip().lower()
    for project_dir, project_name in iter_project_folders(wikiarch_root):
        if project_name.lower() == needle:
            return project_dir, project_name

    raise FileNotFoundError(f"Project not found under {wikiarch_root}: {project}")


def yield_image_files(source_dir: Path):
    """Yield paths to image files in source_dir."""
    for f in source_dir.iterdir():
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS:
            yield f


def extract_project_folder(
    project_dir: Path,
    project_name: str,
    *,
    skip_existing: bool = True,
    output_filename: str = "extractions.json",
    output_path: Path | None = None,
    max_gleaning: int = 1,
    max_workers: int | None = None,
) -> list[dict[str, Any]]:
    """
    Run design-logic extraction for one project folder (images + text assets).

    Concatenates all text files as ref_text for image augmentation, then processes
    each image and each text file (parallel). Output is a flat list of items
    (strategy/goal, image_description, archseek, metadata, etc.) with asset_name.
    If `description.txt` exists, its raw content is also included as:
    {"raw_text": "...", "asset_name": "description.txt"}.

    Args:
        project_dir: Path to the project folder.
        project_name: Human-readable project name.
        skip_existing: Skip if output file already exists.
        output_filename: JSON file name inside project_dir.
        output_path: Explicit output JSON path. If provided, overrides output_filename.
        max_gleaning: Max gleaning rounds per asset.
        max_workers: ThreadPool size (default: min(32, num_cpus + 4)).

    Returns:
        design_analysis: list of dicts.
    """
    out_path = Path(output_path) if output_path is not None else (project_dir / output_filename)
    if skip_existing and out_path.exists():
        with open(out_path, "r", encoding="utf-8") as f:
            return json.load(f)

    image_files = sorted(yield_image_files(project_dir))
    text_files = sorted(yield_text_files(project_dir))
    all_text = "".join(f.read_text(encoding="utf-8") + "\n" for f in text_files)

    design_analysis: list[dict[str, Any]] = []
    description_path = project_dir / "description.txt"
    if description_path.is_file():
        design_analysis.append(
            {
                "raw_text": description_path.read_text(encoding="utf-8"),
                "asset_name": "description.txt",
            }
        )

    def process_image(img_path: Path):
        return extract_image(img_path, project_name, ref_text=all_text or None, max_gleaning=max_gleaning)

    def process_text(txt_path: Path):
        content = txt_path.read_text(encoding="utf-8")
        return extract_text(content, txt_path.name, max_gleaning=max_gleaning)

    with futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        image_futures = [executor.submit(process_image, p) for p in image_files]
        text_futures = [executor.submit(process_text, p) for p in text_files]
        for future in futures.as_completed(image_futures + text_futures):
            design_analysis.extend(future.result())

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(design_analysis, indent=2, ensure_ascii=False), encoding="utf-8")
    return design_analysis


def extract_dataset(
    wikiarch_root: Path,
    *,
    limit: int | None = None,
    skip_existing: bool = True,
    project_output_dir: str = "extraction",
    max_gleaning: int = 1,
    max_workers: int | None = None,
) -> list[list[dict[str, Any]]]:
    """
    Run extraction for every project folder under wikiarch_root.

    Returns:
        List of per-project design_analysis lists.
        Results are saved as one JSON per project under
        <wikiarch_root>/<project_output_dir>/<project_name>.json.
    """
    wikiarch_root, project_root = resolve_wikiarch_paths(wikiarch_root)
    results = []
    for i, (project_dir, project_name) in enumerate(iter_project_folders(project_root)):
        if limit is not None and i >= limit:
            break
        safe_project_name = project_name.replace("/", "_").replace("\\", "_")
        output_path = wikiarch_root / project_output_dir / f"{safe_project_name}.json"
        results.append(
            extract_project_folder(
                project_dir,
                project_name,
                skip_existing=skip_existing,
                output_path=output_path,
                max_gleaning=max_gleaning,
                max_workers=max_workers,
            )
        )
    return results


def main() -> None:
    """CLI: run extraction for all projects or one project."""
    import argparse

    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(
        description="Run design-logic (VLM/LLM) extraction on wikiarch project folders (all or one).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "wikiarch_path",
        type=Path,
        nargs="?",
        default=root / "data" / "wikiarch",
        help="Wikiarch root or project-folder root (e.g. data/wikiarch or data/wikiarch/raw)",
    )
    parser.add_argument("--project", type=str, default=None, help="Run extraction for one project folder name")
    parser.add_argument(
        "--project-output-dir",
        type=str,
        default="extraction",
        help="Output subdirectory under wikiarch root for both all-project and --project modes",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max project folders to process")
    parser.add_argument("--force", action="store_true", help="Re-extract even if output file exists")
    parser.add_argument("--max-gleaning", type=int, default=1, help="Max gleaning rounds per asset")
    parser.add_argument("--max-workers", type=int, default=None, help="ThreadPool max workers")
    args = parser.parse_args()
    wikiarch_root, project_root = resolve_wikiarch_paths(args.wikiarch_path)
    if not project_root.is_dir():
        raise SystemExit(f"Not a directory: {project_root}")

    if args.project:
        try:
            project_dir, project_name = resolve_project_dir(project_root, args.project)
        except FileNotFoundError as e:
            raise SystemExit(str(e)) from e
        safe_project_name = project_name.replace("/", "_").replace("\\", "_")
        output_path = wikiarch_root / args.project_output_dir / f"{safe_project_name}.json"
        result = extract_project_folder(
            project_dir=project_dir,
            project_name=project_name,
            skip_existing=not args.force,
            output_path=output_path,
            max_gleaning=args.max_gleaning,
            max_workers=args.max_workers,
        )
        print(f"Done. Project: {project_name}")
        print(f"Output: {output_path}")
        print(f"Extracted items: {len(result)}")
        if result:
            sample_keys = sorted(result[0].keys())
            print(f"Sample keys: {sample_keys}")
        return

    results = extract_dataset(
        wikiarch_root,
        limit=args.limit,
        skip_existing=not args.force,
        project_output_dir=args.project_output_dir,
        max_gleaning=args.max_gleaning,
        max_workers=args.max_workers,
    )
    print(f"Done. Processed {len(results)} project(s).")


if __name__ == "__main__":
    main()
