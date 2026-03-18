"""知识库管理器。

优先使用 ChromaDB；当运行环境不具备 ChromaDB 时自动回退到内存实现，
保证服务层可用并支持本地联调。
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import loguru

from config.settings import settings
from .retrieval import RetrievalResult, lexical_score

logger = loguru.logger


@dataclass
class _Chunk:
    document_id: str
    chunk_id: str
    text: str
    metadata: Dict[str, Any]


class KnowledgeManager:
    """知识库管理器（Chroma + 内存回退）。"""

    def __init__(self):
        self._chunks: Dict[str, _Chunk] = {}
        self._doc_index: Dict[str, List[str]] = {}
        self._use_chroma = False
        self._collection = None

        try:
            import chromadb  # type: ignore

            persist_dir = Path(settings.chroma_persist_dir)
            persist_dir.mkdir(parents=True, exist_ok=True)
            client = chromadb.PersistentClient(path=str(persist_dir))
            self._collection = client.get_or_create_collection(
                name=settings.chroma_collection_name
            )
            self._use_chroma = True
            logger.info("KnowledgeManager 使用 ChromaDB 后端")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"ChromaDB 初始化失败，回退到内存模式: {e}")

    async def add_document(
        self,
        content: bytes,
        filename: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, List[str]]:
        """添加文档并分块。"""
        document_id = str(uuid.uuid4())
        text = content.decode("utf-8", errors="ignore")
        chunks = self._split_text(text)
        meta = metadata.copy() if metadata else {}
        meta.update(
            {
                "filename": filename,
                "content_hash": hashlib.sha256(content).hexdigest(),
            }
        )

        chunk_ids: List[str] = []
        for idx, chunk_text in enumerate(chunks):
            chunk_id = f"{document_id}_chunk_{idx:04d}"
            chunk_meta = {**meta, "document_id": document_id, "chunk_index": idx}
            chunk_ids.append(chunk_id)
            self._chunks[chunk_id] = _Chunk(
                document_id=document_id,
                chunk_id=chunk_id,
                text=chunk_text,
                metadata=chunk_meta,
            )

        self._doc_index[document_id] = chunk_ids

        if self._use_chroma and self._collection is not None and chunk_ids:
            self._collection.add(
                ids=chunk_ids,
                documents=[self._chunks[c].text for c in chunk_ids],
                metadatas=[self._chunks[c].metadata for c in chunk_ids],
            )

        return document_id, chunk_ids

    async def retrieve_knowledge(
        self,
        query: str,
        n_results: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        use_hybrid: bool = True,
        rerank: bool = True,
    ) -> List[RetrievalResult]:
        """检索知识。"""
        results: List[RetrievalResult] = []

        if self._use_chroma and self._collection is not None:
            try:
                where = filters or None
                query_result = self._collection.query(
                    query_texts=[query],
                    n_results=n_results,
                    where=where,
                )
                ids = query_result.get("ids", [[]])[0]
                docs = query_result.get("documents", [[]])[0]
                metas = query_result.get("metadatas", [[]])[0]
                distances = query_result.get("distances", [[]])[0]

                for idx, chunk_id in enumerate(ids):
                    score = 1.0 - float(distances[idx]) if idx < len(distances) else 0.0
                    meta = metas[idx] if idx < len(metas) else {}
                    text = docs[idx] if idx < len(docs) else ""
                    results.append(
                        RetrievalResult(
                            document_id=str(meta.get("document_id", "")),
                            chunk_id=str(chunk_id),
                            text=text,
                            metadata=meta,
                            relevance_score=max(score, 0.0),
                            retrieval_method="semantic",
                        )
                    )
                return self._post_process(results, query, rerank=rerank)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Chroma 检索失败，使用内存检索回退: {e}")

        for chunk in self._chunks.values():
            if filters and not self._match_filters(chunk.metadata, filters):
                continue
            score = lexical_score(query, chunk.text)
            if score <= 0:
                continue
            results.append(
                RetrievalResult(
                    document_id=chunk.document_id,
                    chunk_id=chunk.chunk_id,
                    text=chunk.text,
                    metadata=chunk.metadata,
                    relevance_score=score,
                    retrieval_method="hybrid" if use_hybrid else "lexical",
                )
            )

        results.sort(key=lambda r: r.relevance_score, reverse=True)
        return self._post_process(results[:n_results], query, rerank=rerank)

    async def get_document_info(self, document_id: str) -> Optional[Dict[str, Any]]:
        chunk_ids = self._doc_index.get(document_id)
        if not chunk_ids:
            return None

        first_chunk = self._chunks.get(chunk_ids[0])
        metadata = first_chunk.metadata if first_chunk else {}
        return {
            "document_id": document_id,
            "chunk_count": len(chunk_ids),
            "metadata": metadata,
        }

    async def update_document(
        self,
        document_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        chunk_ids = self._doc_index.get(document_id)
        if not chunk_ids:
            return False

        patch = metadata or {}
        for chunk_id in chunk_ids:
            chunk = self._chunks.get(chunk_id)
            if chunk:
                chunk.metadata.update(patch)

        if self._use_chroma and self._collection is not None:
            metadatas = [self._chunks[c].metadata for c in chunk_ids if c in self._chunks]
            docs = [self._chunks[c].text for c in chunk_ids if c in self._chunks]
            self._collection.update(ids=chunk_ids, documents=docs, metadatas=metadatas)

        return True

    async def delete_document(self, document_id: str) -> bool:
        chunk_ids = self._doc_index.pop(document_id, [])
        if not chunk_ids:
            return False

        for chunk_id in chunk_ids:
            self._chunks.pop(chunk_id, None)

        if self._use_chroma and self._collection is not None:
            self._collection.delete(ids=chunk_ids)

        return True

    def _split_text(self, text: str, chunk_size: int = 800, overlap: int = 80) -> List[str]:
        if not text:
            return [""]

        chunks: List[str] = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + chunk_size, text_len)
            chunks.append(text[start:end])
            if end == text_len:
                break
            start = max(end - overlap, start + 1)

        return chunks

    def _match_filters(self, metadata: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        for key, expected in filters.items():
            if metadata.get(key) != expected:
                return False
        return True

    def _post_process(
        self,
        results: List[RetrievalResult],
        query: str,
        rerank: bool,
    ) -> List[RetrievalResult]:
        if not rerank:
            return results

        # 简单二次打分：语义分 + 词法分
        for r in results:
            lex = lexical_score(query, r.text)
            r.relevance_score = 0.7 * r.relevance_score + 0.3 * lex

        results.sort(key=lambda r: r.relevance_score, reverse=True)
        return results
