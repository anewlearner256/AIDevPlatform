import asyncio

from core.knowledge_base.knowledge_manager import KnowledgeManager


def test_add_and_retrieve_document():
    km = KnowledgeManager()

    async def run():
        document_id, chunk_ids = await km.add_document(
            content="这是一个登录功能需求说明，包含用户认证和权限控制".encode("utf-8"),
            filename="req.md",
            metadata={"project_id": "p1"},
        )
        assert document_id
        assert len(chunk_ids) >= 1

        results = await km.retrieve_knowledge("登录 权限", n_results=3)
        assert len(results) >= 1
        assert results[0].document_id == document_id

    asyncio.run(run())
