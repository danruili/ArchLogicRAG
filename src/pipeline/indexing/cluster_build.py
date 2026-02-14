from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np
from llama_index.core.bridge.pydantic import Field
from llama_index.core.schema import BaseNode, NodeRelationship, RelatedNodeInfo, TextNode, TransformComponent
from llama_index.embeddings.openai import OpenAIEmbedding

from .cluster_utils import cluster_nodes, summarize_clusters


class ClusterBuild(TransformComponent):
    """Compatibility cluster transform mirroring legacy summary hierarchy build."""

    working_dir: str = Field(default="data/wikiarch/index")
    max_depth: int = Field(default=2)
    min_cluster_num: int = Field(default=30)
    embedding_model: str = Field(default="text-embedding-3-large")
    embedding_dimensions: int = Field(default=1024)

    def __call__(self, nodes: Sequence[BaseNode], **kwargs):
        all_nodes_dict = {node.node_id: node for node in nodes}
        max_case_id = max(int(node.metadata.get("case_id", 0)) for node in nodes) if nodes else 0

        strategy_nodes: list[TextNode] = []
        goal_nodes: list[TextNode] = []
        other_nodes: list[TextNode] = []

        for node in nodes:
            if not isinstance(node, TextNode):
                continue
            node_type = node.metadata.get("type")
            if node_type == "strategy":
                strategy_nodes.append(node)
            elif node_type == "goal":
                goal_nodes.append(node)
            else:
                other_nodes.append(node)

        matrix_dir = Path(self.working_dir) / "cluster_matrix"
        matrix_dir.mkdir(parents=True, exist_ok=True)

        summaries: list[TextNode] = []
        embedder = OpenAIEmbedding(model=self.embedding_model, dimensions=self.embedding_dimensions)

        for node_type, working_nodes in (("strategy", strategy_nodes), ("goal", goal_nodes)):
            current = working_nodes
            for depth in range(self.max_depth):
                if len(current) <= self.min_cluster_num:
                    break
                new_summaries = create_summary_nodes(
                    current,
                    all_nodes_dict,
                    node_type=node_type,
                    depth=depth,
                    max_case_id=max_case_id,
                    matrix_dir=matrix_dir,
                    embedder=embedder,
                )
                summaries.extend(new_summaries)
                for summary in new_summaries:
                    all_nodes_dict[summary.node_id] = summary
                current = new_summaries

        return strategy_nodes + goal_nodes + summaries + other_nodes


def create_summary_nodes(
    nodes: list[TextNode],
    all_nodes_dict: dict[str, TextNode],
    node_type: str,
    depth: int,
    max_case_id: int,
    matrix_dir: Path,
    embedder: OpenAIEmbedding,
) -> list[TextNode]:
    clusters, _ = cluster_nodes(nodes)
    summary_dicts = summarize_clusters(clusters, all_nodes_dict, node_type)

    num_groups = len(clusters)
    group_matrix = np.zeros((max_case_id + 1, num_groups))

    summaries: list[TextNode] = []
    for cluster_id, group_nodes in clusters.items():
        summary = summary_dicts[cluster_id]

        involved_cases: set[int] = set()
        for node in group_nodes:
            case_id = node.metadata.get("case_id")
            if isinstance(case_id, int):
                involved_cases.add(case_id)
            elif isinstance(case_id, str):
                for item in case_id.split(","):
                    if item.strip().isdigit():
                        involved_cases.add(int(item.strip()))

        if involved_cases:
            group_matrix[list(involved_cases), cluster_id] += 1

        summary_node = TextNode(
            text=str(summary["description"]),
            metadata={
                "type": f"{node_type}_summary",
                "headline": str(summary["headline"]),
                "depth": depth,
                "case_id": ",".join(str(x) for x in sorted(involved_cases)),
            },
            excluded_llm_metadata_keys=["type", "depth"],
            excluded_embed_metadata_keys=["type", "depth"],
        )
        summary_node.embedding = embedder.get_text_embedding(
            f"#{summary['headline']}\n{summary['description']}"
        )

        parent_links = summary_node.relationships.get(NodeRelationship.CHILD, [])
        for node in group_nodes:
            link = node.relationships.get(NodeRelationship.PARENT, [])
            link.append(
                RelatedNodeInfo(node_id=summary_node.node_id, metadata={"type": node_type, "depth": depth})
            )
            node.relationships[NodeRelationship.PARENT] = link
            parent_links.append(
                RelatedNodeInfo(node_id=node.node_id, metadata={"type": node_type, "depth": depth})
            )
        summary_node.relationships[NodeRelationship.CHILD] = parent_links

        summaries.append(summary_node)

    np.save(matrix_dir / f"{node_type}_group_matrix_{depth}.npy", group_matrix)
    return summaries
