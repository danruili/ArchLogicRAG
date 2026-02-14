from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Sequence

import numpy as np
from llama_index.core.schema import BaseNode, NodeRelationship, TextNode
from tenacity import retry, stop_after_attempt, wait_fixed

from src.common import llm_client


SUMMARY_PROMPT = """
You are an architecture designer critic. Summarize the provided design {node_type} references.
Return one JSON object inside a ```json block with fields:
{{
  "headline": "one-line summary",
  "description": "detailed structured synthesis that keeps reference ids in [R..A..] form"
}}

Inputs:
{inputs}
""".strip()

STRATEGY_TEMPLATE = """
-----
Reference ID: [{reference_id}]
{strategy} (serves for: {goal})
""".strip()

GOAL_TEMPLATE = """
-----
Reference ID: [{reference_id}]
{goal} (achieved by: {strategy})
""".strip()

GROUP_TEMPLATE = """
-----
Headline: {headline}
Content: {description}
""".strip()


def cluster_nodes(nodes: list[BaseNode], umap_dim: int = 10, given_n: int | None = None) -> tuple[dict[int, list[BaseNode]], list[int]]:
    # Local imports keep this module importable when optional deps are missing.
    from sklearn.mixture import GaussianMixture
    from umap import UMAP

    embeddings = [node.embedding for node in nodes if node.embedding is not None]
    if len(embeddings) != len(nodes):
        raise ValueError("All nodes must have embeddings before clustering")

    emb = np.array(embeddings)
    reducer = UMAP(
        n_components=umap_dim,
        n_neighbors=15,
        min_dist=0.1,
        metric="cosine",
        random_state=42,
    )
    reduced = reducer.fit_transform(emb)

    labels = None
    best_bic = float("inf")
    n_choices = [given_n] if given_n is not None else [i for i in range(30, 240, 5)]

    for n in n_choices:
        if n is None or n >= len(embeddings):
            break
        gmm = GaussianMixture(n_components=n, covariance_type="full", random_state=42)
        gmm.fit(reduced)
        pred = gmm.predict(reduced)
        bic = gmm.bic(reduced)
        if bic < best_bic:
            best_bic = bic
            labels = pred
        elif bic > best_bic:
            break

    if labels is None:
        labels = np.zeros((len(nodes),), dtype=int)

    clusters: dict[int, list[BaseNode]] = {}
    for label in np.unique(labels):
        lid = int(label)
        clusters[lid] = [node for node, node_label in zip(nodes, labels) if node_label == label]

    return clusters, [int(x) for x in labels]


def stringify_nodes(group_nodes: Sequence[TextNode], all_nodes_dict: dict[str, TextNode], node_type: str) -> str:
    text = []
    for node in group_nodes:
        if "headline" not in node.metadata:
            case_id = node.metadata["case_id"]
            asset_id = node.metadata["asset_id"]
            reference_id = f"R{case_id}A{asset_id}"
            if node_type == "strategy":
                goal_id = node.relationships[NodeRelationship.NEXT].node_id
                goal_node = all_nodes_dict[goal_id]
                text.append(STRATEGY_TEMPLATE.format(strategy=node.text, goal=goal_node.text, reference_id=reference_id))
            else:
                strategy_id = node.relationships[NodeRelationship.PREVIOUS].node_id
                strategy_node = all_nodes_dict[strategy_id]
                text.append(GOAL_TEMPLATE.format(strategy=strategy_node.text, goal=node.text, reference_id=reference_id))
        else:
            text.append(
                GROUP_TEMPLATE.format(
                    headline=node.metadata["headline"],
                    description=node.text,
                )
            )
    return "\n".join(text)


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def summarize_group(stringified_nodes: str, node_type: str) -> dict:
    prompt = SUMMARY_PROMPT.format(inputs=stringified_nodes, node_type=node_type)
    response = llm_client.chat([{"role": "user", "content": prompt}], model=llm_client.get_text_model())

    match = re.findall(r"```json\s*(.*?)\s*```", response, re.DOTALL)
    if not match:
        raise ValueError("No JSON block returned by summarizer")

    data = json.loads(match[-1])
    if not isinstance(data, dict) or "headline" not in data or "description" not in data:
        raise ValueError("Invalid summary response format")
    return data


def summarize_clusters(clusters: dict[int, list[TextNode]], all_nodes_dict: dict[str, TextNode], node_type: str) -> dict[int, dict]:
    stringified = {
        cluster_id: stringify_nodes(group_nodes, all_nodes_dict, node_type)
        for cluster_id, group_nodes in clusters.items()
    }

    def _job(item: tuple[int, str]) -> tuple[int, dict]:
        cid, payload = item
        return cid, summarize_group(payload, node_type)

    summaries: dict[int, dict] = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        for cid, data in executor.map(_job, stringified.items()):
            summaries[cid] = data
    return summaries
