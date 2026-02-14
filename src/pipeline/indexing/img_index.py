"""Image embedding index builder for WikiArch assets."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from src.common.llm_client import _load_project_env_once

VALID_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}


@dataclass(slots=True)
class ImageIndexConfig:
    raw_dir: Path = Path("data/wikiarch/raw")
    reference_dir: Path = Path("data/wikiarch/index/reference")
    output_dir: Path = Path("data/wikiarch/index/img_index")
    asset_map_filename: str = "asset_id_map.json"
    max_workers: int = 4
    show_progress: bool = True
    validate_paths: bool = True
    max_size_kb: int = 256


@dataclass(slots=True)
class ImageBuildStats:
    total_assets: int
    image_assets: int
    embedded_images: int
    missing_files: int
    embedding_dim: int
    output_dir: str


class ArchDataImageIndexer:
    def __init__(self, config: ImageIndexConfig | None = None) -> None:
        _load_project_env_once()
        self.config = config or ImageIndexConfig()

    @property
    def asset_map_path(self) -> Path:
        return self.config.reference_dir / self.config.asset_map_filename

    def _load_asset_id_map(self) -> dict[str, str]:
        path = self.asset_map_path
        if not path.is_file():
            raise FileNotFoundError(
                f"asset id map not found: {path}. Build text index first to generate it."
            )
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError(f"Invalid asset id map format in {path}")
        return {str(k): str(v) for k, v in data.items()}

    def _iter_image_records(self, asset_id_map: dict[str, str]) -> list[dict]:
        records: list[dict] = []
        for asset_id, mapped in asset_id_map.items():
            if "|||" not in mapped:
                continue
            case_name, asset_name = mapped.split("|||", 1)
            ext = Path(asset_name).suffix.lower()
            if ext not in VALID_IMAGE_EXTS:
                continue

            image_path = self.config.raw_dir / case_name / asset_name
            records.append(
                {
                    "asset_id": asset_id,
                    "case_name": case_name,
                    "image_name": asset_name,
                    "image_path": str(image_path),
                    "exists": image_path.is_file(),
                }
            )
        return records

    def build(self, *, force: bool = False) -> ImageBuildStats:
        if not os.environ.get("REPLICATE_API_TOKEN"):
            raise ValueError("REPLICATE_API_TOKEN must be set for image embedding indexing")

        try:
            from src.common.replicate_api import batch_image_embeddings
        except ImportError as e:
            raise ImportError(
                "Image indexing requires the 'replicate' dependency. Install dependencies with uv sync."
            ) from e

        asset_id_map = self._load_asset_id_map()
        records = self._iter_image_records(asset_id_map)

        image_paths = [r["image_path"] for r in records]
        embeddings = batch_image_embeddings(
            image_paths=image_paths,
            max_workers=self.config.max_workers,
            show_progress=self.config.show_progress,
            validate_paths=self.config.validate_paths,
            max_size_kb=self.config.max_size_kb,
        )

        if len(embeddings) != len(records):
            raise RuntimeError(
                "Embedding output length mismatch. "
                f"expected {len(records)}, got {len(embeddings)}"
            )

        valid_rows: list[dict] = []
        valid_embeddings: list[list[float]] = []
        missing_files = 0
        for record, emb in zip(records, embeddings):
            if not record["exists"]:
                missing_files += 1
            if emb is None:
                continue
            valid_rows.append(record)
            valid_embeddings.append(emb)

        if not valid_embeddings:
            raise RuntimeError("No image embeddings were produced.")

        arr = np.asarray(valid_embeddings, dtype=np.float32)

        out_dir = self.config.output_dir
        if out_dir.exists() and force:
            (out_dir / "embeddings.npy").unlink(missing_ok=True)
            (out_dir / "records.json").unlink(missing_ok=True)
            (out_dir / "meta.json").unlink(missing_ok=True)
        out_dir.mkdir(parents=True, exist_ok=True)

        np.save(out_dir / "embeddings.npy", arr)
        with open(out_dir / "records.json", "w", encoding="utf-8") as f:
            json.dump(valid_rows, f, ensure_ascii=False, indent=2)

        meta = {
            "embedding_dim": int(arr.shape[1]),
            "embedded_images": int(arr.shape[0]),
            "image_assets": len(records),
            "total_assets": len(asset_id_map),
            "missing_files": missing_files,
            "raw_dir": str(self.config.raw_dir),
            "asset_map_path": str(self.asset_map_path),
        }
        with open(out_dir / "meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        return ImageBuildStats(
            total_assets=len(asset_id_map),
            image_assets=len(records),
            embedded_images=int(arr.shape[0]),
            missing_files=missing_files,
            embedding_dim=int(arr.shape[1]),
            output_dir=str(out_dir),
        )

    def info(self) -> dict:
        out_dir = self.config.output_dir
        meta_path = out_dir / "meta.json"
        if not meta_path.is_file():
            return {
                "output_dir": str(out_dir),
                "exists": False,
                "message": "No image index found. Run build first.",
            }

        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        meta["output_dir"] = str(out_dir)
        meta["exists"] = True
        return meta


def config_from_env() -> ImageIndexConfig:
    _load_project_env_once()
    return ImageIndexConfig(
        raw_dir=Path(os.environ.get("INDEX_RAW_DIR", "data/wikiarch/raw")),
        reference_dir=Path(os.environ.get("INDEX_REFERENCE_DIR", "data/wikiarch/index/reference")),
        output_dir=Path(os.environ.get("IMG_INDEX_OUTPUT_DIR", "data/wikiarch/index/img_index")),
        max_workers=int(os.environ.get("IMG_INDEX_MAX_WORKERS", "4")),
        show_progress=os.environ.get("IMG_INDEX_SHOW_PROGRESS", "1") not in {"0", "false", "False"},
        validate_paths=os.environ.get("IMG_INDEX_VALIDATE_PATHS", "1") not in {"0", "false", "False"},
        max_size_kb=int(os.environ.get("IMG_INDEX_MAX_SIZE_KB", "256")),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="WikiArch image indexing runner")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="Build image embedding index from raw project images")
    build.add_argument("--force", action="store_true", help="Overwrite existing image index artifacts")
    build.add_argument("--raw-dir", default=None, help="Root directory of raw WikiArch projects")
    build.add_argument("--reference-dir", default=None, help="Directory containing asset_id_map.json")
    build.add_argument("--output-dir", default=None, help="Directory for image index outputs")
    build.add_argument("--max-workers", type=int, default=None, help="Parallel workers for embedding requests")
    build.add_argument("--no-progress", action="store_true", help="Disable image embedding progress bar")
    build.add_argument("--no-validate-paths", action="store_true", help="Skip image path existence checks")
    build.add_argument("--max-size-kb", type=int, default=None, help="Max image size for preprocessing")

    info = sub.add_parser("info", help="Show image index metadata")
    info.add_argument("--output-dir", default=None, help="Directory for image index outputs")

    return parser


def _with_overrides(args: argparse.Namespace) -> ImageIndexConfig:
    cfg = config_from_env()
    if getattr(args, "raw_dir", None):
        cfg.raw_dir = Path(args.raw_dir)
    if getattr(args, "reference_dir", None):
        cfg.reference_dir = Path(args.reference_dir)
    if getattr(args, "output_dir", None):
        cfg.output_dir = Path(args.output_dir)
    if getattr(args, "max_workers", None) is not None:
        cfg.max_workers = int(args.max_workers)
    if getattr(args, "no_progress", False):
        cfg.show_progress = False
    if getattr(args, "no_validate_paths", False):
        cfg.validate_paths = False
    if getattr(args, "max_size_kb", None) is not None:
        cfg.max_size_kb = int(args.max_size_kb)
    return cfg


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    cfg = _with_overrides(args)
    indexer = ArchDataImageIndexer(cfg)

    if args.command == "build":
        stats = indexer.build(force=bool(args.force))
        print(
            json.dumps(
                {
                    "total_assets": stats.total_assets,
                    "image_assets": stats.image_assets,
                    "embedded_images": stats.embedded_images,
                    "missing_files": stats.missing_files,
                    "embedding_dim": stats.embedding_dim,
                    "output_dir": stats.output_dir,
                },
                indent=2,
            )
        )
        return

    if args.command == "info":
        print(json.dumps(indexer.info(), indent=2))
        return

    raise ValueError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
