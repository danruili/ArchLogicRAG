"""Modern ChromaDB indexer that follows the legacy ingestion pipeline stages."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import chromadb
from llama_index.core import Document, StorageContext, VectorStoreIndex
from llama_index.core.ingestion import IngestionPipeline
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore

from src.common.llm_client import _load_project_env_once

from .cluster_build import ClusterBuild
from .ingestion_parser import DesignLogicParser


@dataclass(slots=True)
class IndexConfig:
    extraction_dir: Path = Path("data/wikiarch/extraction")
    persist_dir: Path = Path("data/wikiarch/index/chroma")
    reference_dir: Path = Path("data/wikiarch/index/reference")
    workspace_dir: Path = Path("data/wikiarch/index")
    collection_name: str = "wikiarch_logic"
    embedding_model: str = "text-embedding-3-large"
    embedding_dimensions: int = 1024
    enable_cluster: bool = True
    show_progress: bool = True


@dataclass(slots=True)
class BuildStats:
    project_count: int
    node_count: int
    collection_name: str
    persist_dir: str


class ArchDataChromaIndexer:
    def __init__(self, config: IndexConfig | None = None) -> None:
        _load_project_env_once()
        self.config = config or IndexConfig()

    def _iter_project_files(self) -> list[Path]:
        root = self.config.extraction_dir
        if not root.is_dir():
            raise FileNotFoundError(f"extraction directory not found: {root}")
        return sorted(p for p in root.iterdir() if p.is_file() and p.suffix == ".json")

    def _collect_case_documents(self) -> tuple[list[Document], dict[int, str]]:
        docs: list[Document] = []
        case_id_map: dict[int, str] = {}

        for case_id, project_file in enumerate(self._iter_project_files()):
            case_name = project_file.stem
            docs.append(Document(metadata={"case_name": case_name, "case_id": case_id}))
            case_id_map[case_id] = case_name

        return docs, case_id_map

    def _pipeline(self) -> IngestionPipeline:
        transforms = [
            DesignLogicParser(
                extraction_dir=str(self.config.extraction_dir),
                reference_dir=str(self.config.reference_dir),
            ),
            OpenAIEmbedding(
                model=self.config.embedding_model,
                dimensions=self.config.embedding_dimensions,
            ),
        ]

        if self.config.enable_cluster:
            transforms.append(
                ClusterBuild(
                    working_dir=str(self.config.workspace_dir),
                    embedding_model=self.config.embedding_model,
                    embedding_dimensions=self.config.embedding_dimensions,
                )
            )

        return IngestionPipeline(transformations=transforms)

    def _persist_case_map(self, case_id_map: dict[int, str]) -> None:
        self.config.reference_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config.reference_dir / "case_id_map.json", "w", encoding="utf-8") as f:
            json.dump(case_id_map, f, indent=2)

    def _new_vector_store(self, force: bool) -> ChromaVectorStore:
        self.config.persist_dir.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(self.config.persist_dir))

        if force:
            existing = {c.name for c in client.list_collections()}
            if self.config.collection_name in existing:
                client.delete_collection(self.config.collection_name)

        collection = client.get_or_create_collection(self.config.collection_name)
        return ChromaVectorStore(chroma_collection=collection)

    def build(self, force: bool = False, show_progress: bool | None = None) -> BuildStats:
        docs, case_id_map = self._collect_case_documents()
        use_progress = self.config.show_progress if show_progress is None else show_progress
        nodes = self._pipeline().run(documents=docs, show_progress=use_progress)

        self._persist_case_map(case_id_map)

        vector_store = self._new_vector_store(force=force)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        VectorStoreIndex(nodes, storage_context=storage_context)

        return BuildStats(
            project_count=len(case_id_map),
            node_count=len(nodes),
            collection_name=self.config.collection_name,
            persist_dir=str(self.config.persist_dir),
        )

    def load(self) -> VectorStoreIndex:
        vector_store = self._new_vector_store(force=False)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        embed_model = OpenAIEmbedding(
            model=self.config.embedding_model,
            dimensions=self.config.embedding_dimensions,
        )
        return VectorStoreIndex.from_vector_store(
            vector_store=vector_store,
            storage_context=storage_context,
            embed_model=embed_model,
        )

    def query(self, query_text: str, top_k: int = 5) -> list[dict]:
        index = self.load()
        retriever = index.as_retriever(similarity_top_k=top_k)
        results = retriever.retrieve(query_text)
        return [
            {
                "score": item.score,
                "node_id": item.node.node_id,
                "text": item.node.text,
                "metadata": item.node.metadata,
            }
            for item in results
        ]

    def collection_count(self) -> int:
        client = chromadb.PersistentClient(path=str(self.config.persist_dir))
        collection = client.get_or_create_collection(self.config.collection_name)
        return int(collection.count())


def config_from_env() -> IndexConfig:
    _load_project_env_once()
    return IndexConfig(
        extraction_dir=Path(os.environ.get("INDEX_EXTRACTION_DIR", "data/wikiarch/extraction")),
        persist_dir=Path(os.environ.get("CHROMA_PERSIST_DIR", "data/wikiarch/index/chroma")),
        reference_dir=Path(os.environ.get("INDEX_REFERENCE_DIR", "data/wikiarch/index/reference")),
        workspace_dir=Path(os.environ.get("INDEX_WORKSPACE_DIR", "data/wikiarch/index")),
        collection_name=os.environ.get("CHROMA_COLLECTION_NAME", "wikiarch_logic"),
        embedding_model=os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large"),
        embedding_dimensions=int(os.environ.get("OPENAI_EMBEDDING_DIM", "1024")),
        enable_cluster=os.environ.get("INDEX_ENABLE_CLUSTER", "1") not in {"0", "false", "False"},
        show_progress=os.environ.get("INDEX_SHOW_PROGRESS", "1") not in {"0", "false", "False"},
    )
