import logging
from pathlib import Path

import nest_asyncio
from llama_index.core.schema import NodeWithScore, TextNode
from llama_index.embeddings.openai import OpenAIEmbedding

from src.pipeline.indexing.chroma_index import ArchDataChromaIndexer, config_from_env

from .img_retrieve import ImageRetriever
from .retriever_utils.fusion_search import rrf_fusion
from .retriever_utils.retriever_filters import RETRIEVER_FILTERS


ARCHSEEK_TEMPLATE = """
Case Name: {case_name}
Ref ID: R{case_id}A{asset_id}
Score: {score:.2f}
{content}
"""

SUMMARY_TEMPLATE = """
Summary: {summary}
Score: {score:.2f}
"""


class DesignLogicRetriever:
    def __init__(
        self,
        index_root: str = "data/wikiarch/index",
        top_k: int = 20,
    ):
        nest_asyncio.apply()
        self.top_k = top_k
        self.logger = logging.getLogger("DesignRetriever")

        cfg = config_from_env()
        root = Path(index_root)
        cfg.persist_dir = root / "chroma"
        cfg.reference_dir = root / "reference"
        cfg.workspace_dir = root

        indexer = ArchDataChromaIndexer(cfg)
        self.index = indexer.load()
        self.embed_model = OpenAIEmbedding(
            model=cfg.embedding_model,
            dimensions=cfg.embedding_dimensions,
        )

        # Check the index is not empty without relying on vector store internals.
        collection_count = indexer.collection_count()
        if collection_count == 0:
            raise ValueError(
                "The Chroma index is empty at "
                f"'{cfg.persist_dir}' for collection '{cfg.collection_name}'. "
                "Build it with: uv run python -m src.pipeline.indexing.runner build --force"
            )
        else:
            self.logger.info(
                f"Chroma index loaded with {collection_count} records from '{cfg.persist_dir}'."
            )
        
        self.image_retriever = ImageRetriever(index_root=str(root))

    def general_dense_retrieve(
        self,
        query: str,
        mode: str = "default",
        top_k: int = 20,
    ) -> list[NodeWithScore]:
        """
        Retrieve top-k results for a given query and filter mode.
        """
        dense_retriever = self.index.as_retriever(
            similarity_top_k=top_k,
            filters=RETRIEVER_FILTERS[mode],
            embed_model=self.embed_model,
        )

        try:
            response: list[NodeWithScore] = dense_retriever.retrieve(query)
        except Exception as e:
            self.logger.error(f"Error retrieving results: {e}")
            response = []

        return response

    def qa_retrieve(
        self,
        query: str,
        top_k: int = 20,
        retrieve_top_k: int = 100,
        drop_summary: bool = False,
        drop_non_summary: bool = False,
    ) -> tuple[str, list[dict]]:
        """
        Retrieve top-k results for QA generation.
        """
        self.logger.info(f"Retrieving results for query: {query}")

        if drop_non_summary and drop_summary:
            raise ValueError("Cannot drop both non-summary and summary results.")

        if not drop_summary:
            summary_response = self.general_dense_retrieve(query, mode="summary", top_k=5)
            summary_results = [
                {"summary": item.node.text, "score": item.score, "type": "summary"}
                for item in summary_response
            ]
        else:
            summary_results = []

        if drop_non_summary and not drop_summary:
            return self.stringify_results(summary_results), summary_results

        archseek_results = [
            self.__node_with_score_to_dict(item)
            for item in self.general_dense_retrieve(query, mode="archseek", top_k=retrieve_top_k)
        ]
        default_results = [
            self.__node_with_score_to_dict(item)
            for item in self.general_dense_retrieve(query, mode="default", top_k=retrieve_top_k)
        ]
        image_results = self.image_retriever.retrieve_asset_by_text(query, top_k=retrieve_top_k)

        archseek_asset_ids = list(dict.fromkeys(item["asset_id"] for item in archseek_results))
        default_asset_ids = list(dict.fromkeys(item["asset_id"] for item in default_results))
        image_asset_ids = list(dict.fromkeys(item["asset_id"] for item in image_results))

        self.logger.info(
            "RRF fusion with %s archseek, %s image, and %s default results.",
            len(archseek_asset_ids),
            len(image_asset_ids),
            len(default_asset_ids),
        )

        min_length = min(len(archseek_asset_ids), len(image_asset_ids), len(default_asset_ids))
        if min_length > 0:
            fused_asset_ids = rrf_fusion(
                archseek_asset_ids[:min_length],
                image_asset_ids[:min_length],
                default_asset_ids[:min_length],
            )
        else:
            fused_asset_ids = archseek_asset_ids or default_asset_ids

        archseek_by_asset = {item["asset_id"]: item for item in archseek_results}
        default_by_asset = {item["asset_id"]: item for item in default_results}
        archseek_rank = {asset_id: idx for idx, asset_id in enumerate(archseek_asset_ids)}
        default_rank = {asset_id: idx for idx, asset_id in enumerate(default_asset_ids)}

        final_results = []
        for asset_id in fused_asset_ids:
            in_archseek = asset_id in archseek_by_asset
            in_default = asset_id in default_by_asset
            if not in_archseek and not in_default:
                continue
            if in_archseek and not in_default:
                final_results.append(archseek_by_asset[asset_id])
                continue
            if in_default and not in_archseek:
                final_results.append(default_by_asset[asset_id])
                continue
            if archseek_rank[asset_id] <= default_rank[asset_id]:
                final_results.append(archseek_by_asset[asset_id])
            else:
                final_results.append(default_by_asset[asset_id])

        final_results = final_results[:top_k]
        all_results = summary_results + final_results
        return self.stringify_results(all_results), all_results

    def __node_with_score_to_dict(self, node_with_score: NodeWithScore) -> dict:
        node = node_with_score.node
        return {
            "content": node.text,
            "score": node_with_score.score,
            "asset_id": node.metadata["asset_id"],
            "case_name": node.metadata["case_name"],
            "case_id": node.metadata["case_id"],
            "type": node.metadata["type"],
        }

    def stringify_results(self, results: list[dict]) -> str:
        final_results = []
        for item in results:
            if item["type"] == "summary":
                final_results.append(
                    SUMMARY_TEMPLATE.format(summary=item["summary"], score=item["score"])
                )
            else:
                final_results.append(
                    ARCHSEEK_TEMPLATE.format(
                        case_name=item["case_name"],
                        case_id=item["case_id"],
                        asset_id=item["asset_id"],
                        score=item["score"],
                        content=item["content"],
                    )
                )
        return "\n".join(final_results)

    def case_search(self, query: str, mode: str = "default") -> list[dict]:
        """
        Retrieve unique case results for a given query.
        """
        response = self.general_dense_retrieve(query, mode=mode, top_k=500)

        final_results = []
        case_name_set = set()
        for item in response:
            node: TextNode = item.node
            case_name = node.metadata["case_name"]
            if case_name in case_name_set:
                continue
            final_results.append(self.__node_with_score_to_dict(item))
            case_name_set.add(case_name)

        return final_results[: self.top_k]
