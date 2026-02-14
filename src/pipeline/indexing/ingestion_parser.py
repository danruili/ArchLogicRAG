from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from llama_index.core.bridge.pydantic import Field
from llama_index.core.node_parser import NodeParser
from llama_index.core.schema import BaseNode, NodeRelationship, RelatedNodeInfo, TextNode
from llama_index.core.utils import get_tqdm_iterable


class DesignLogicParser(NodeParser):
    """Compatibility parser mirroring the legacy design-logic node extraction flow."""

    extraction_dir: str = Field(default="data/wikiarch/extraction")
    reference_dir: str = Field(default="data/wikiarch/index/reference")

    def __init__(self, extraction_dir: str, reference_dir: str, **kwargs):
        super().__init__(extraction_dir=extraction_dir, reference_dir=reference_dir, **kwargs)

    def _parse_nodes(self, nodes: Iterable[BaseNode], show_progress: bool = False, **kwargs) -> list[BaseNode]:
        all_nodes: list[BaseNode] = []
        asset_id_map: dict[str, int] = {}

        for node in get_tqdm_iterable(nodes, show_progress, "Parsing design logic"):
            case_name = node.metadata["case_name"]
            case_id = node.metadata["case_id"]
            json_file = Path(self.extraction_dir) / f"{case_name}.json"
            if not json_file.is_file():
                raise FileNotFoundError(f"json not found: {json_file}")

            with open(json_file, "r", encoding="utf-8") as f:
                case_json = json.load(f)
            if not isinstance(case_json, list):
                continue

            for node_dict in case_json:
                if not isinstance(node_dict, dict):
                    continue

                asset_name = str(node_dict.get("asset_name") or "unknown_asset")
                map_key = f"{case_name}|||{asset_name}"
                if map_key not in asset_id_map:
                    asset_id_map[map_key] = len(asset_id_map)
                node_dict["asset_id"] = asset_id_map[map_key]

                if "strategy" in node_dict and "goal" in node_dict:
                    strategy, goal, pair = create_logic_nodes(node_dict, case_name, case_id)
                    all_nodes.extend([strategy, goal, pair])
                elif "image_description" in node_dict:
                    all_nodes.extend(create_nodes_by_paragraph(node_dict, case_name, case_id))
                elif "image_analysis" in node_dict:
                    all_nodes.extend(
                        create_nodes_by_paragraph(node_dict, case_name, case_id, field="image_analysis")
                    )
                elif "augmented_image_description" in node_dict:
                    all_nodes.extend(
                        create_nodes_by_paragraph(
                            node_dict,
                            case_name,
                            case_id,
                            field="augmented_image_description",
                        )
                    )
                elif "archseek" in node_dict:
                    all_nodes.extend(create_archseek_nodes(node_dict, case_name, case_id))
                elif "raw_text" in node_dict:
                    all_nodes.extend(create_raw_txt_nodes(node_dict, case_name, case_id))

        # Persist reverse map: asset_id -> case|||asset
        reverse_map = {v: k for k, v in asset_id_map.items()}
        ref_dir = Path(self.reference_dir)
        ref_dir.mkdir(parents=True, exist_ok=True)
        with open(ref_dir / "asset_id_map.json", "w", encoding="utf-8") as f:
            json.dump(reverse_map, f, indent=2)

        return all_nodes


def _excluded_embed_metadata() -> list[str]:
    return ["case_name", "asset_name", "type", "round", "case_id", "asset_id", "subject"]


def create_logic_nodes(logic: dict, case_name: str, case_id: int) -> tuple[BaseNode, BaseNode, BaseNode]:
    strategy = TextNode(
        text=str(logic["strategy"]),
        metadata={
            "case_name": case_name,
            "case_id": case_id,
            "asset_name": logic.get("asset_name", "unknown_asset"),
            "asset_id": logic["asset_id"],
            "type": "strategy",
            "round": int(logic.get("round", 1)),
        },
        excluded_llm_metadata_keys=["asset_name", "type", "round"],
        excluded_embed_metadata_keys=_excluded_embed_metadata(),
    )
    goal = TextNode(
        text=str(logic["goal"]),
        metadata={
            "case_name": case_name,
            "case_id": case_id,
            "asset_name": logic.get("asset_name", "unknown_asset"),
            "asset_id": logic["asset_id"],
            "type": "goal",
            "round": int(logic.get("round", 1)),
        },
        excluded_llm_metadata_keys=["asset_name", "type", "round"],
        excluded_embed_metadata_keys=_excluded_embed_metadata(),
    )
    pair = TextNode(
        text=f"{strategy.text.rstrip(',.')}, so as to {goal.text}",
        metadata={
            "case_name": case_name,
            "case_id": case_id,
            "asset_name": logic.get("asset_name", "unknown_asset"),
            "asset_id": logic["asset_id"],
            "type": "pair",
            "round": int(logic.get("round", 1)),
        },
        excluded_llm_metadata_keys=["asset_name", "type", "round"],
        excluded_embed_metadata_keys=_excluded_embed_metadata(),
    )

    strategy.relationships[NodeRelationship.NEXT] = RelatedNodeInfo(node_id=goal.node_id)
    goal.relationships[NodeRelationship.PREVIOUS] = RelatedNodeInfo(node_id=strategy.node_id)
    return strategy, goal, pair


def create_nodes_by_paragraph(logic: dict, case_name: str, case_id: int, field: str = "image_description") -> list[BaseNode]:
    value = logic.get(field)
    if not isinstance(value, str):
        return []

    out: list[BaseNode] = []
    for paragraph in value.split("\n\n"):
        text = paragraph.strip()
        if not text:
            continue
        out.append(
            TextNode(
                text=text,
                metadata={
                    "case_name": case_name,
                    "case_id": case_id,
                    "asset_name": logic.get("asset_name", "unknown_asset"),
                    "asset_id": logic["asset_id"],
                    "type": field,
                },
                excluded_llm_metadata_keys=["asset_name", "type"],
                excluded_embed_metadata_keys=_excluded_embed_metadata(),
            )
        )
    return out


def create_archseek_nodes(logic: dict, case_name: str, case_id: int) -> list[BaseNode]:
    archseek = logic.get("archseek")
    if not isinstance(archseek, dict):
        return []

    out: list[BaseNode] = []
    for subject, values in archseek.items():
        if not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, str) or not item.strip():
                continue
            out.append(
                TextNode(
                    text=item,
                    metadata={
                        "case_name": case_name,
                        "case_id": case_id,
                        "asset_name": logic.get("asset_name", "unknown_asset"),
                        "asset_id": logic["asset_id"],
                        "type": "archseek",
                        "subject": str(subject),
                    },
                    excluded_llm_metadata_keys=["asset_name", "type"],
                    excluded_embed_metadata_keys=_excluded_embed_metadata(),
                )
            )
    return out


def create_raw_txt_nodes(logic: dict, case_name: str, case_id: int) -> list[BaseNode]:
    raw_text = logic.get("raw_text")
    if not isinstance(raw_text, str):
        return []

    chunk_size = 280
    stride = 200
    min_length = 80
    chunks = [raw_text[i:i + chunk_size] for i in range(0, len(raw_text), stride)]
    if len(chunks) > 1 and len(chunks[-1]) < min_length:
        chunks[-2] += chunks[-1]
        chunks.pop()

    out: list[BaseNode] = []
    for chunk in chunks:
        text = chunk.strip()
        if not text:
            continue
        out.append(
            TextNode(
                text=text,
                metadata={
                    "case_name": case_name,
                    "case_id": case_id,
                    "asset_name": logic.get("asset_name", "unknown_asset"),
                    "asset_id": logic["asset_id"],
                    "type": "raw_text",
                },
                excluded_llm_metadata_keys=["asset_name", "type"],
                excluded_embed_metadata_keys=_excluded_embed_metadata(),
            )
        )
    return out
