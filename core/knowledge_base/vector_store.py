"""向量存储初始化入口。"""

from __future__ import annotations

from typing import Optional

from .knowledge_manager import KnowledgeManager

_manager: Optional[KnowledgeManager] = None


def init_vector_store() -> KnowledgeManager:
    """初始化并返回全局知识库管理器。"""
    global _manager
    if _manager is None:
        _manager = KnowledgeManager()
    return _manager


def get_vector_store() -> KnowledgeManager:
    """获取已初始化的知识库管理器。"""
    return init_vector_store()
