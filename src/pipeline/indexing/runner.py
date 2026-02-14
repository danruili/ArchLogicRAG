from __future__ import annotations

import argparse
import json
from pathlib import Path

from .chroma_index import ArchDataChromaIndexer, IndexConfig, config_from_env


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="WikiArch indexing runner (ChromaDB)")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="Build Chroma index from extraction JSON files")
    build.add_argument("--force", action="store_true", help="Replace the existing Chroma collection")
    build.add_argument("--no-cluster", action="store_true", help="Disable cluster/summarization transform")
    build.add_argument("--no-progress", action="store_true", help="Disable indexing progress bars")
    build.add_argument("--extraction-dir", default=None, help="Directory of extracted project JSON files")
    build.add_argument("--persist-dir", default=None, help="Chroma persist directory")
    build.add_argument("--reference-dir", default=None, help="Directory for case/asset id maps")
    build.add_argument("--workspace-dir", default=None, help="Workspace directory for cluster artifacts")
    build.add_argument("--collection", default=None, help="Chroma collection name")

    query = sub.add_parser("query", help="Run similarity search")
    query.add_argument("text", help="Query text")
    query.add_argument("--top-k", type=int, default=5, help="Top-k results")
    query.add_argument("--persist-dir", default=None, help="Chroma persist directory")
    query.add_argument("--collection", default=None, help="Chroma collection name")

    info = sub.add_parser("info", help="Show index metadata")
    info.add_argument("--persist-dir", default=None, help="Chroma persist directory")
    info.add_argument("--collection", default=None, help="Chroma collection name")
    info.add_argument("--extraction-dir", default=None, help="Directory of extracted project JSON files")

    return parser


def _with_overrides(args: argparse.Namespace) -> IndexConfig:
    cfg = config_from_env()
    if getattr(args, "extraction_dir", None):
        cfg.extraction_dir = Path(args.extraction_dir)
    if getattr(args, "persist_dir", None):
        cfg.persist_dir = Path(args.persist_dir)
    if getattr(args, "reference_dir", None):
        cfg.reference_dir = Path(args.reference_dir)
    if getattr(args, "workspace_dir", None):
        cfg.workspace_dir = Path(args.workspace_dir)
    if getattr(args, "collection", None):
        cfg.collection_name = args.collection
    if getattr(args, "no_cluster", False):
        cfg.enable_cluster = False
    if getattr(args, "no_progress", False):
        cfg.show_progress = False
    return cfg


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    cfg = _with_overrides(args)
    indexer = ArchDataChromaIndexer(cfg)

    if args.command == "build":
        stats = indexer.build(force=bool(args.force), show_progress=cfg.show_progress)
        print(
            json.dumps(
                {
                    "project_count": stats.project_count,
                    "node_count": stats.node_count,
                    "collection_name": stats.collection_name,
                    "persist_dir": stats.persist_dir,
                    "cluster_enabled": cfg.enable_cluster,
                    "show_progress": cfg.show_progress,
                },
                indent=2,
            )
        )
        return

    if args.command == "query":
        results = indexer.query(args.text, top_k=args.top_k)
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    if args.command == "info":
        extraction_files = 0
        if cfg.extraction_dir.is_dir():
            extraction_files = len(list(cfg.extraction_dir.glob("*.json")))
        print(
            json.dumps(
                {
                    "collection_name": cfg.collection_name,
                    "persist_dir": str(cfg.persist_dir),
                    "extraction_dir": str(cfg.extraction_dir),
                    "extraction_project_files": extraction_files,
                    "collection_count": indexer.collection_count(),
                    "cluster_enabled": cfg.enable_cluster,
                    "show_progress": cfg.show_progress,
                },
                indent=2,
            )
        )
        return

    raise ValueError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
