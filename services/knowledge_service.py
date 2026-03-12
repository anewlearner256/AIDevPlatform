"""知识库服务

管理RAG知识库的业务逻辑。
"""

from typing import List, Dict, Any, Optional
import loguru

from core.knowledge_base.knowledge_manager import KnowledgeManager
from core.knowledge_base.retrieval import RetrievalResult
from models.schemas import (
    KnowledgeDocumentCreate,
    KnowledgeDocumentUpdate,
    KnowledgeDocumentResponse,
    KnowledgeRetrievalRequest,
    KnowledgeRetrievalResponse,
    RetrievalResultResponse,
)
from models.database import get_async_session
from models.database import KnowledgeDocument as KnowledgeDocumentModel

logger = loguru.logger

class KnowledgeService:
    """知识库服务"""

    def __init__(self):
        self.knowledge_manager = KnowledgeManager()

    async def add_document(
        self,
        content: bytes,
        filename: str,
        document_data: KnowledgeDocumentCreate
    ) -> Dict[str, Any]:
        """
        添加文档到知识库

        Args:
            content: 文档内容
            filename: 文件名
            document_data: 文档数据

        Returns:
            添加结果
        """
        try:
            # 添加到知识库管理器
            document_id, chunk_ids = await self.knowledge_manager.add_document(
                content=content,
                filename=filename,
                metadata=document_data.metadata
            )

            # 保存到数据库
            async with get_async_session() as session:
                db_document = KnowledgeDocumentModel(
                    id=document_id,
                    filename=filename,
                    file_path=None,  # 文件路径在知识库管理器中
                    project_id=document_data.project_id,
                    document_type=document_data.document_type,
                    chunk_count=len(chunk_ids),
                    vector_store_ids=chunk_ids,
                    metadata=document_data.metadata
                )

                session.add(db_document)
                await session.commit()
                await session.refresh(db_document)

            # 构建响应
            result = {
                "document_id": document_id,
                "filename": filename,
                "chunk_count": len(chunk_ids),
                "chunk_ids": chunk_ids,
            }

            logger.info(f"文档添加成功: {filename}，ID: {document_id}")
            return result

        except Exception as e:
            logger.error(f"添加文档失败: {filename}，错误: {str(e)}")
            raise

    async def retrieve_knowledge(
        self,
        request: KnowledgeRetrievalRequest
    ) -> KnowledgeRetrievalResponse:
        """
        检索知识

        Args:
            request: 检索请求

        Returns:
            检索响应
        """
        try:
            # 执行检索
            results = await self.knowledge_manager.retrieve_knowledge(
                query=request.query,
                n_results=request.n_results,
                filters=request.filters,
                use_hybrid=request.use_hybrid,
                rerank=request.rerank
            )

            # 转换为响应格式
            result_responses = [
                RetrievalResultResponse(
                    document_id=result.document_id,
                    chunk_id=result.chunk_id,
                    text=result.text,
                    metadata=result.metadata,
                    relevance_score=result.relevance_score,
                    retrieval_method=result.retrieval_method
                )
                for result in results
            ]

            response = KnowledgeRetrievalResponse(
                query=request.query,
                results=result_responses,
                total_results=len(result_responses)
            )

            logger.info(f"知识检索成功: '{request.query}'，返回 {len(result_responses)} 个结果")
            return response

        except Exception as e:
            logger.error(f"知识检索失败: {str(e)}")
            raise

    async def get_document(self, document_id: str) -> Optional[KnowledgeDocumentResponse]:
        """
        获取文档信息

        Args:
            document_id: 文档ID

        Returns:
            文档信息
        """
        try:
            # 从数据库获取
            async with get_async_session() as session:
                db_document = await session.get(KnowledgeDocumentModel, document_id)
                if not db_document:
                    return None

                # 从知识库管理器获取更多信息
                kb_info = await self.knowledge_manager.get_document_info(document_id)

                # 构建响应
                response = KnowledgeDocumentResponse(
                    id=db_document.id,
                    filename=db_document.filename,
                    project_id=db_document.project_id,
                    file_path=db_document.file_path,
                    document_type=db_document.document_type,
                    content_hash=db_document.content_hash,
                    chunk_count=db_document.chunk_count,
                    vector_store_ids=db_document.vector_store_ids or [],
                    metadata=db_document.metadata or {},
                    created_at=db_document.created_at,
                    updated_at=db_document.updated_at
                )

                # 合并知识库信息
                if kb_info:
                    response.metadata.update(kb_info.get("metadata", {}))

                return response

        except Exception as e:
            logger.error(f"获取文档失败: {document_id}，错误: {str(e)}")
            raise

    async def update_document(
        self,
        document_id: str,
        update_data: KnowledgeDocumentUpdate
    ) -> bool:
        """
        更新文档

        Args:
            document_id: 文档ID
            update_data: 更新数据

        Returns:
            是否成功
        """
        try:
            # 更新数据库
            async with get_async_session() as session:
                db_document = await session.get(KnowledgeDocumentModel, document_id)
                if not db_document:
                    return False

                # 更新字段
                if update_data.document_type is not None:
                    db_document.document_type = update_data.document_type

                if update_data.metadata is not None:
                    # 合并元数据
                    current_metadata = db_document.metadata or {}
                    current_metadata.update(update_data.metadata)
                    db_document.metadata = current_metadata

                await session.commit()

            # 更新知识库管理器中的元数据
            success = await self.knowledge_manager.update_document(
                document_id=document_id,
                metadata=update_data.metadata
            )

            if success:
                logger.info(f"文档更新成功: {document_id}")
                return True
            else:
                logger.warning(f"文档更新失败（知识库）: {document_id}")
                return False

        except Exception as e:
            logger.error(f"更新文档失败: {document_id}，错误: {str(e)}")
            return False

    async def delete_document(self, document_id: str) -> bool:
        """
        删除文档

        Args:
            document_id: 文档ID

        Returns:
            是否成功
        """
        try:
            # 从知识库管理器删除
            kb_success = await self.knowledge_manager.delete_document(document_id)

            # 从数据库删除
            async with get_async_session() as session:
                db_document = await session.get(KnowledgeDocumentModel, document_id)
                if db_document:
                    await session.delete(db_document)
                    await session.commit()

            if kb_success:
                logger.info(f"文档删除成功: {document_id}")
                return True
            else:
                logger.warning(f"文档删除失败（知识库）: {document_id}")
                return False

        except Exception as e:
            logger.error(f"删除文档失败: {document_id}，错误: {str(e)}")
            return False

    async def list_documents(
        self,
        project_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[KnowledgeDocumentResponse]:
        """
        列出文档

        Args:
            project_id: 项目ID（可选）
            skip: 跳过数量
            limit: 返回数量

        Returns:
            文档列表
        """
        try:
            async with get_async_session() as session:
                from sqlalchemy import select
                from sqlalchemy.sql import func

                # 构建查询
                query = select(KnowledgeDocumentModel)

                if project_id:
                    query = query.where(KnowledgeDocumentModel.project_id == project_id)

                # 计数
                count_query = select(func.count()).select_from(KnowledgeDocumentModel)
                if project_id:
                    count_query = count_query.where(KnowledgeDocumentModel.project_id == project_id)

                total = await session.scalar(count_query)

                # 分页
                query = query.offset(skip).limit(limit)
                query = query.order_by(KnowledgeDocumentModel.created_at.desc())

                # 执行查询
                result = await session.execute(query)
                db_documents = result.scalars().all()

                # 转换为响应
                documents = []
                for db_doc in db_documents:
                    doc_response = KnowledgeDocumentResponse(
                        id=db_doc.id,
                        filename=db_doc.filename,
                        project_id=db_doc.project_id,
                        file_path=db_doc.file_path,
                        document_type=db_doc.document_type,
                        content_hash=db_doc.content_hash,
                        chunk_count=db_doc.chunk_count,
                        vector_store_ids=db_doc.vector_store_ids or [],
                        metadata=db_doc.metadata or {},
                        created_at=db_doc.created_at,
                        updated_at=db_doc.updated_at
                    )
                    documents.append(doc_response)

                logger.info(f"列出文档成功，项目ID: {project_id}，总数: {total}")
                return documents

        except Exception as e:
            logger.error(f"列出文档失败: {str(e)}")
            raise

    async def get_knowledge_base_stats(self) -> Dict[str, Any]:
        """
        获取知识库统计信息

        Returns:
            统计信息
        """
        try:
            # 从知识库管理器获取统计
            kb_stats = await self.knowledge_manager.get_knowledge_base_stats()

            # 从数据库获取统计
            async with get_async_session() as session:
                from sqlalchemy import select, func

                # 文档统计
                doc_count_query = select(func.count()).select_from(KnowledgeDocumentModel)
                total_documents = await session.scalar(doc_count_query)

                # 按类型统计
                type_query = select(
                    KnowledgeDocumentModel.document_type,
                    func.count(KnowledgeDocumentModel.id)
                ).group_by(KnowledgeDocumentModel.document_type)

                result = await session.execute(type_query)
                type_stats = {row[0] or "unknown": row[1] for row in result}

            # 合并统计信息
            stats = {
                "total_documents": total_documents,
                "document_types": type_stats,
                "knowledge_base": kb_stats,
            }

            logger.info(f"获取知识库统计成功，总文档数: {total_documents}")
            return stats

        except Exception as e:
            logger.error(f"获取知识库统计失败: {str(e)}")
            raise

    async def search_documents(
        self,
        query: str,
        document_type: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: int = 20
    ) -> List[KnowledgeDocumentResponse]:
        """
        搜索文档（基于元数据）

        Args:
            query: 搜索查询
            document_type: 文档类型过滤
            project_id: 项目ID过滤
            limit: 返回数量

        Returns:
            文档列表
        """
        try:
            # 首先进行知识检索
            retrieval_request = KnowledgeRetrievalRequest(
                query=query,
                n_results=limit,
                use_hybrid=True,
                rerank=True
            )

            retrieval_response = await self.retrieve_knowledge(retrieval_request)

            # 提取文档ID
            document_ids = list(set([result.document_id for result in retrieval_response.results]))

            # 从数据库获取文档信息
            documents = []
            for doc_id in document_ids[:limit]:
                doc = await self.get_document(doc_id)
                if doc:
                    # 应用过滤
                    if document_type and doc.document_type != document_type:
                        continue
                    if project_id and doc.project_id != project_id:
                        continue
                    documents.append(doc)

            logger.info(f"文档搜索成功: '{query}'，返回 {len(documents)} 个结果")
            return documents

        except Exception as e:
            logger.error(f"文档搜索失败: {str(e)}")
            raise

    async def clear_knowledge_base(self, confirm: bool = False) -> bool:
        """
        清空知识库

        Args:
            confirm: 确认标志

        Returns:
            是否成功
        """
        if not confirm:
            logger.warning("清空知识库需要确认")
            return False

        try:
            # 重置向量存储
            vector_store = self.knowledge_manager.vector_store
            success = vector_store.reset_collection()

            if success:
                # 删除所有数据库记录
                async with get_async_session() as session:
                    from sqlalchemy import delete
                    await session.execute(delete(KnowledgeDocumentModel))
                    await session.commit()

                logger.warning("知识库已清空")
                return True
            else:
                logger.error("清空知识库失败（向量存储）")
                return False

        except Exception as e:
            logger.error(f"清空知识库失败: {str(e)}")
            return False