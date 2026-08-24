"""向量 + 中文 BM25 的轻量混合检索。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import jieba
from rank_bm25 import BM25L


def _tokenize(text: str) -> List[str]:
    """使用 jieba 切分中文，同时保留英文、数字与下划线。"""
    return [
        token
        for token in jieba.lcut(text.lower())
        if re.search(r"[\w\u4e00-\u9fff]", token)
    ]


@dataclass
class SearchCandidate:
    """一个候选文档块及其融合分数。"""

    chunk_id: str
    document: Any
    fusion_score: float = 0.0
    relevance_score: float | None = None


class BM25Index:
    """适合当前单文档 Demo 的内存 BM25 索引。"""

    def __init__(self, chunks: Sequence[Any]):
        self.chunks = list(chunks)
        if not self.chunks:
            raise ValueError("无法为无文本块的文档创建 BM25 索引")
        corpus = [_tokenize(doc.page_content) for doc in self.chunks]
        self._index = BM25L(corpus)

    def search(self, query: str, k: int) -> List[Any]:
        if not self.chunks:
            return []
        scores = self._index.get_scores(_tokenize(query))
        ranked_indexes = sorted(
            range(len(self.chunks)),
            key=lambda index: float(scores[index]),
            reverse=True,
        )
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
            # rrf_k 用来削弱相邻名次的分差；同一块被多路召回时分数会在这里累加。
            current_score = 1 / (rrf_k + rank)
            scores[chunk_id] = scores.get(chunk_id, 0.0) + current_score
    return scores


def _chunk_id(document: Any) -> str:
    chunk_id = document.metadata.get("chunk_id")
    if not chunk_id:
        raise ValueError("资料块缺少 chunk_id，请先通过资料入库流程处理")
    return str(chunk_id)


def hybrid_retrieve(
    query: str,
    vector_store: Any,
    keyword_index: BM25Index,
    per_route_k: int,
    fusion_k: int,
    original_query: str | None = None,
) -> Tuple[List[SearchCandidate], Dict[str, Any]]:
    """对改写问题和原问题分别执行向量、BM25 召回，再使用 RRF 融合。"""
    query_routes = [("rewritten", query)]
    if original_query and original_query.strip() and original_query.strip() != query.strip():
        query_routes.append(("original", original_query.strip()))

    rankings: Dict[str, List[str]] = {}
    route_documents: List[Any] = []
    for route_name, route_query in query_routes:
        vector_docs = vector_store.similarity_search(route_query, k=per_route_k)
        keyword_docs = keyword_index.search(route_query, k=per_route_k)
        rankings[f"vector_{route_name}"] = [_chunk_id(doc) for doc in vector_docs]
        rankings[f"keyword_{route_name}"] = [_chunk_id(doc) for doc in keyword_docs]
        route_documents.extend([*vector_docs, *keyword_docs])

    scores = reciprocal_rank_fusion(rankings)

    documents: Dict[str, Any] = {}
    # 四路结果可能包含同一个块，以 chunk_id 为键既能去重，也能累加它在不同查询中的排名分数。
    for doc in route_documents:
        documents[_chunk_id(doc)] = doc

    candidates: List[SearchCandidate] = []
    for chunk_id, score in scores.items():
        if chunk_id not in documents:
            continue
        candidates.append(
            SearchCandidate(
                chunk_id=chunk_id,
                document=documents[chunk_id],
                fusion_score=float(score),
            )
        )

    candidates.sort(key=lambda item: item.fusion_score, reverse=True)
    candidates = candidates[:fusion_k]
    debug = {
        "queries": {name: value for name, value in query_routes},
        "route_rankings": rankings,
        "vector_chunk_ids": rankings["vector_rewritten"],
        "keyword_chunk_ids": rankings["keyword_rewritten"],
        "fusion_chunk_ids": [item.chunk_id for item in candidates],
        "fusion_method": "rrf",
    }
    return candidates, debug
