"""知识检索数据结构与工具函数。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List
import math
import re


@dataclass
class RetrievalResult:
    """检索结果。"""

    document_id: str
    chunk_id: str
    text: str
    metadata: Dict[str, Any]
    relevance_score: float
    retrieval_method: str = "semantic"


def _tokenize(text: str) -> List[str]:
    return [t for t in re.split(r"\W+", (text or "").lower()) if t]


def lexical_score(query: str, text: str) -> float:
    """轻量词法相似度（Jaccard）。"""
    q = set(_tokenize(query))
    t = set(_tokenize(text))
    if not q or not t:
        return 0.0
    return len(q & t) / len(q | t)


def normalize_scores(results: List[RetrievalResult]) -> List[RetrievalResult]:
    """对结果分值做归一化。"""
    if not results:
        return results

    scores = [r.relevance_score for r in results]
    max_score = max(scores)
    min_score = min(scores)

    if math.isclose(max_score, min_score):
        for r in results:
            r.relevance_score = 1.0
        return results

    gap = max_score - min_score
    for r in results:
        r.relevance_score = (r.relevance_score - min_score) / gap
    return results
