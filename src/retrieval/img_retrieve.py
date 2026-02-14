import json
import logging
from pathlib import Path

import numpy as np

from src.common.replicate_api import batch_text_embeddings


class ImageRetriever:
    def __init__(self, index_root: str = "data/wikiarch/index"):
        self.index_root = Path(index_root)

        img_index_dir = self.index_root / "img_index"
        reference_dir = self.index_root / "reference"
        self.img_embs_np = np.load(img_index_dir / "embeddings.npy")
        with open(img_index_dir / "records.json", "r", encoding="utf-8") as f:
            self.records = json.load(f)
        with open(reference_dir / "case_id_map.json", "r", encoding="utf-8") as f:
            case_id_map = json.load(f)
        self.case_id_map = {v: int(k) for k, v in case_id_map.items()}

        self.embedding_cache_path = img_index_dir / "embedding_cache.json"
        if self.embedding_cache_path.exists():
            with open(self.embedding_cache_path, "r", encoding="utf-8") as f:
                self.embedding_cache = json.load(f)
        else:
            self.embedding_cache = {}
    
    def _text_to_embedding(
            self, 
            text: str,
            )-> np.ndarray:
        """
        Convert text to embedding using the multimodal embeddings API.
        """
        if text in self.embedding_cache:
            return np.array(self.embedding_cache[text])
        else:
            # get the embedding of the text query
            logging.info(f"fetching query embedding from Multimodal Embedding APIs: {text}")
            embedding = batch_text_embeddings([text])[0]
            logging.info("query embedding fetched from Multimodal Embedding APIs.")
            if embedding is None:
                raise RuntimeError("Failed to generate text embedding from Multimodal Embedding APIs.")
            # save the embedding to cache
            self.embedding_cache[text] = embedding
            # save the cache to file
            with open(self.embedding_cache_path, "w", encoding="utf-8") as f:
                json.dump(self.embedding_cache, f, ensure_ascii=False, indent=4)
        
            # normalize the embedding
            embedding = embedding / np.linalg.norm(embedding)
            return embedding

    def retrieve_asset_by_text(
            self,
            query_text: str,
            top_k: int = 50,
        )-> list[dict]:
        """
        Retrieve assets by text query.
        Return the top k asset ids.
        """
        # get the embedding of the text query
        query_embedding = self._text_to_embedding(query_text)

        # calculate the similarity
        similarities = np.dot(self.img_embs_np, query_embedding)

        # sort the similarities
        sorted_indices = np.argsort(similarities)[::-1]

        # get the corresponding asset ids
        sorted_asset_ids = [self.records[i]["asset_id"] for i in sorted_indices]

        # only keep the first appearance of each asset id
        results = []
        seen_asset_ids = set()
        for i, asset_id in enumerate(sorted_asset_ids):
            if asset_id in seen_asset_ids:
                continue
            seen_asset_ids.add(asset_id)
            record = self.records[sorted_indices[i]]
            if record["case_name"] not in self.case_id_map:
                continue
            results.append({
                "type": "image",
                "score": float(similarities[sorted_indices[i]]),
                "case_id": self.case_id_map[record["case_name"]],
                "case_name": record["case_name"],
                "asset_id": asset_id,
            })

        # get the top k results
        top_k_results = results[:top_k]

        return top_k_results
    
