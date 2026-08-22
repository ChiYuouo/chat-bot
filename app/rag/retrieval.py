"""向量 + 中文 BM25 的轻量混合检索。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import jieba
from rank_bm25 import BM25Okapi


def _tokenize(text: str) -> List[str]:
    """使用 jieba 切分中文，同时保留英文、数字与下划线。"""
    return [
        token
        for token in jieba.lcut(text.lower())
        if re.search(r"[\w\u4e00-\u9fff]", token)
    ]


@dataclass
class SearchCandidate:
    """一个候选文档块及其在各检索阶段的排名信息。"""

    chunk_id: str
    document: Any
    vector_rank: Optional[int] = None
    keyword_rank: Optional[int] = None
    fusion_score: float = 0.0
    rerank_rank: Optional[int] = None


class BM25Index:
    """适合当前单文档 Demo 的内存 BM25 索引。"""

    def __init__(self, chunks: Sequence[Any]):
        self.chunks = list(chunks)
        corpus = [_tokenize(doc.page_content) for doc in self.chunks]
        self._index = BM25Okapi(corpus)

    def search(self, query: str, k: int) -> List[Any]:
        if not self.chunks:
            return []
        scores = self._index.get_scores(_tokenize(query))
        ranked_indexes = sorted(
            range(len(self.chunks)),
            key=lambda index: float(scores[index]),
            reverse=True,
        )
        # 分数为 0 说明查询词完全没有命中，不能把无关块塞进混排。
        return [
            self.chunks[index]
            for index in ranked_indexes[:k]
            if float(scores[index]) > 0
        ]


def reciprocal_rank_fusion(
    rankings: Mapping[str, Sequence[str]],
    rrf_k: int = 60,
) -> Dict[str, float]:
    """合并多路排序，返回 ``chunk_id -> RRF 分数``。"""
    scores: Dict[str, float] = {}
    for chunk_ids in rankings.values():
        for rank, chunk_id in enumerate(chunk_ids, start=1):
            current_score = 1 / (rrf_k + rank)
            scores[chunk_id] = scores.get(chunk_id, 0.0) + current_score
    return scores


def _chunk_id(document: Any) -> str:
    chunk_id = document.metadata.get("chunk_id")
    if not chunk_id:
        raise ValueError("文档块缺少 chunk_id，请先通过 process_pdf 处理文档")
    return str(chunk_id)


def hybrid_retrieve(
    query: str,
    vector_store: Any,
    keyword_index: BM25Index,
    per_route_k: int,
    fusion_k: int,
) -> Tuple[List[SearchCandidate], Dict[str, Any]]:
    """执行向量、BM25 两路召回，并使用 RRF 融合结果。"""
    vector_docs = vector_store.similarity_search(query, k=per_route_k)
    keyword_docs = keyword_index.search(query, k=per_route_k)

    rankings = {
        "vector": [_chunk_id(doc) for doc in vector_docs],
        "keyword": [_chunk_id(doc) for doc in keyword_docs],
    }
    scores = reciprocal_rank_fusion(rankings)

    documents: Dict[str, Any] = {}
    for doc in [*vector_docs, *keyword_docs]:
        documents[_chunk_id(doc)] = doc

    candidates: List[SearchCandidate] = []
    for chunk_id, score in scores.items():
        if chunk_id not in documents:
            continue
        candidates.append(
            SearchCandidate(
                chunk_id=chunk_id,
                document=documents[chunk_id],
                vector_rank=(rankings["vector"].index(chunk_id) + 1)
                if chunk_id in rankings["vector"]
                else None,
                keyword_rank=(rankings["keyword"].index(chunk_id) + 1)
                if chunk_id in rankings["keyword"]
                else None,
                fusion_score=float(score),
            )
        )

    candidates.sort(key=lambda item: item.fusion_score, reverse=True)
    candidates = candidates[:fusion_k]
    debug = {
        "vector_chunk_ids": rankings["vector"],
        "keyword_chunk_ids": rankings["keyword"],
        "fusion_chunk_ids": [item.chunk_id for item in candidates],
        "fusion_method": "rrf",
    }
    return candidates, debug
