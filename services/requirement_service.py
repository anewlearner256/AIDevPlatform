"""需求服务

处理需求文档上传、分析和需求智能体交互。
"""

import asyncio
from typing import List, Dict, Any, Optional
import loguru
from fastapi import BackgroundTasks

from models.schemas import (
    RequirementCreate,
    RequirementUpdate,
    RequirementResponse,
    RequirementAnalysisResponse,
    DocumentUploadResponse,
)
from models.database import get_async_session
from models.database import Requirement as RequirementModel
from models.database import Project as ProjectModel
from services.knowledge_service import KnowledgeService
from core.agents.requirement_agent import RequirementAgent
from utils.llm_client import LLMClient

logger = loguru.logger

class RequirementService:
    """需求服务"""

    def __init__(self):
        self.knowledge_service = KnowledgeService()
        self.requirement_agent = RequirementAgent()
        self.llm_client = LLMClient.get_default()

    async def process_document(
        self,
        content: bytes,
        filename: str,
        project_id: Optional[str] = None,
        document_type: str = "requirement"
    ) -> DocumentUploadResponse:
        """
        处理需求文档

        Args:
            content: 文档内容
            filename: 文件名
            project_id: 项目ID
            document_type: 文档类型

        Returns:
            文档上传响应
        """
        try:
            # 准备文档数据
            from models.schemas import KnowledgeDocumentCreate
            document_data = KnowledgeDocumentCreate(
                filename=filename,
                document_type=document_type,
                project_id=project_id,
                metadata={
                    "source": "requirement_upload",
                    "original_filename": filename,
                    "project_id": project_id,
                }
            )

            # 添加到知识库
            result = await self.knowledge_service.add_document(
                content=content,
                filename=filename,
                document_data=document_data
            )

            # 创建需求记录
            async with get_async_session() as session:
                # 验证项目存在
                if project_id:
                    project = await session.get(ProjectModel, project_id)
                    if not project:
                        raise ValueError(f"项目不存在: {project_id}")

                # 创建需求
                requirement = RequirementModel(
                    title=filename,
                    description=f"从文档 '{filename}' 导入的需求",
                    project_id=project_id,
                    document_path=result.get("file_path"),
                    status="pending",
                    metadata={
                        "document_id": result["document_id"],
                        "chunk_ids": result["chunk_ids"],
                        "original_filename": filename,
                    }
                )

                session.add(requirement)
                await session.commit()
                await session.refresh(requirement)

            response = DocumentUploadResponse(
                document_id=result["document_id"],
                filename=filename,
                message="文档上传成功",
                chunk_count=result["chunk_count"]
            )

            logger.info(f"需求文档处理成功: {filename}，需求ID: {requirement.id}")
            return response

        except Exception as e:
            logger.error(f"需求文档处理失败: {filename}，错误: {str(e)}")
            raise

    async def start_analysis(
        self,
        requirement: RequirementCreate,
        background_tasks: BackgroundTasks
    ) -> str:
        """
        启动需求分析

        Args:
            requirement: 需求创建数据
            background_tasks: 后台任务

        Returns:
            任务ID
        """
        try:
            import uuid
            task_id = str(uuid.uuid4())

            # 创建需求记录
            async with get_async_session() as session:
                # 验证项目存在
                project = await session.get(ProjectModel, requirement.project_id)
                if not project:
                    raise ValueError(f"项目不存在: {requirement.project_id}")

                # 创建需求
                db_requirement = RequirementModel(
                    title=requirement.title,
                    description=requirement.description,
                    project_id=requirement.project_id,
                    document_path=requirement.document_path,
                    priority=requirement.priority,
                    status="analyzing",
                    metadata=requirement.metadata
                )

                session.add(db_requirement)
                await session.commit()
                await session.refresh(db_requirement)

                requirement_id = db_requirement.id

            # 添加后台分析任务
            background_tasks.add_task(
                self._analyze_requirement_background,
                requirement_id=requirement_id,
                task_id=task_id
            )

            logger.info(f"需求分析任务已启动: {requirement_id}，任务ID: {task_id}")
            return task_id

        except Exception as e:
            logger.error(f"启动需求分析失败: {str(e)}")
            raise

    async def _analyze_requirement_background(self, requirement_id: str, task_id: str):
        """后台需求分析任务"""
        try:
            logger.info(f"开始后台需求分析: {requirement_id}")

            async with get_async_session() as session:
                # 获取需求
                requirement = await session.get(RequirementModel, requirement_id)
                if not requirement:
                    logger.error(f"需求不存在: {requirement_id}")
                    return

                # 更新状态为分析中
                requirement.status = "analyzing"
                await session.commit()

                # 准备分析数据
                analysis_data = {
                    "requirement_id": requirement_id,
                    "title": requirement.title,
                    "description": requirement.description,
                    "document_path": requirement.document_path,
                    "metadata": requirement.metadata or {},
                }

                # 如果有文档路径，从知识库检索相关文档
                if requirement.document_path or requirement.metadata.get("document_id"):
                    try:
                        # 检索相关知识
                        from models.schemas import KnowledgeRetrievalRequest
                        retrieval_request = KnowledgeRetrievalRequest(
                            query=f"{requirement.title} {requirement.description or ''}",
                            n_results=5,
                            use_hybrid=True
                        )

                        knowledge_response = await self.knowledge_service.retrieve_knowledge(
                            retrieval_request
                        )

                        # 将检索结果添加到分析数据
                        if knowledge_response.results:
                            analysis_data["related_knowledge"] = [
                                {
                                    "text": result.text[:500],  # 截取前500字符
                                    "source": result.metadata.get("filename", "unknown"),
                                    "relevance": result.relevance_score
                                }
                                for result in knowledge_response.results
                            ]

                    except Exception as e:
                        logger.warning(f"知识检索失败，继续分析: {str(e)}")

                # 调用需求智能体进行分析
                try:
                    analysis_result = await self.requirement_agent.process(analysis_data)

                    # 更新需求状态和分析结果
                    requirement.analysis_result = analysis_result
                    requirement.status = "analyzed"
                    requirement.metadata = {
                        **(requirement.metadata or {}),
                        "analysis_task_id": task_id,
                        "analysis_completed": True,
                    }

                    await session.commit()

                    logger.info(f"需求分析完成: {requirement_id}")

                except Exception as e:
                    logger.error(f"需求智能体分析失败: {requirement_id}，错误: {str(e)}")

                    # 更新为失败状态
                    requirement.status = "failed"
                    requirement.metadata = {
                        **(requirement.metadata or {}),
                        "analysis_error": str(e),
                        "analysis_task_id": task_id,
                    }

                    await session.commit()

        except Exception as e:
            logger.error(f"后台需求分析任务失败: {requirement_id}，错误: {str(e)}")

    async def get_requirement(self, requirement_id: str) -> Optional[RequirementResponse]:
        """
        获取需求详情

        Args:
            requirement_id: 需求ID

        Returns:
            需求响应
        """
        try:
            async with get_async_session() as session:
                requirement = await session.get(RequirementModel, requirement_id)
                if not requirement:
                    return None

                # 转换为响应格式
                response = RequirementResponse(
                    id=requirement.id,
                    project_id=requirement.project_id,
                    title=requirement.title,
                    description=requirement.description,
                    document_path=requirement.document_path,
                    analysis_result=requirement.analysis_result,
                    status=requirement.status,
                    priority=requirement.priority,
                    created_by=requirement.created_by,
                    created_at=requirement.created_at,
                    updated_at=requirement.updated_at,
                    metadata=requirement.metadata or {},
                )

                return response

        except Exception as e:
            logger.error(f"获取需求失败: {requirement_id}，错误: {str(e)}")
            raise

    async def get_analysis_result(self, requirement_id: str) -> Optional[Dict[str, Any]]:
        """
        获取需求分析结果

        Args:
            requirement_id: 需求ID

        Returns:
            分析结果
        """
        try:
            async with get_async_session() as session:
                requirement = await session.get(RequirementModel, requirement_id)
                if not requirement or requirement.status != "analyzed":
                    return None

                return requirement.analysis_result

        except Exception as e:
            logger.error(f"获取分析结果失败: {requirement_id}，错误: {str(e)}")
            raise

    async def get_project_requirements(
        self,
        project_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[RequirementResponse]:
        """
        获取项目的所有需求

        Args:
            project_id: 项目ID
            skip: 跳过数量
            limit: 返回数量

        Returns:
            需求列表
        """
        try:
            async with get_async_session() as session:
                from sqlalchemy import select
                from sqlalchemy.sql import func

                # 验证项目存在
                project = await session.get(ProjectModel, project_id)
                if not project:
                    raise ValueError(f"项目不存在: {project_id}")

                # 构建查询
                query = select(RequirementModel).where(
                    RequirementModel.project_id == project_id
                )

                # 计数
                count_query = select(func.count()).where(
                    RequirementModel.project_id == project_id
                )
                total = await session.scalar(count_query)

                # 分页和排序
                query = query.offset(skip).limit(limit)
                query = query.order_by(RequirementModel.created_at.desc())

                # 执行查询
                result = await session.execute(query)
                requirements = result.scalars().all()

                # 转换为响应
                responses = []
                for req in requirements:
                    response = RequirementResponse(
                        id=req.id,
                        project_id=req.project_id,
                        title=req.title,
                        description=req.description,
                        document_path=req.document_path,
                        analysis_result=req.analysis_result,
                        status=req.status,
                        priority=req.priority,
                        created_by=req.created_by,
                        created_at=req.created_at,
                        updated_at=req.updated_at,
                        metadata=req.metadata or {},
                    )
                    responses.append(response)

                logger.info(f"获取项目需求成功: {project_id}，总数: {total}")
                return responses

        except Exception as e:
            logger.error(f"获取项目需求失败: {project_id}，错误: {str(e)}")
            raise

    async def update_requirement(
        self,
        requirement_id: str,
        update_data: RequirementUpdate
    ) -> bool:
        """
        更新需求

        Args:
            requirement_id: 需求ID
            update_data: 更新数据

        Returns:
            是否成功
        """
        try:
            async with get_async_session() as session:
                requirement = await session.get(RequirementModel, requirement_id)
                if not requirement:
                    return False

                # 更新字段
                if update_data.title is not None:
                    requirement.title = update_data.title

                if update_data.description is not None:
                    requirement.description = update_data.description

                if update_data.status is not None:
                    requirement.status = update_data.status

                if update_data.priority is not None:
                    requirement.priority = update_data.priority

                if update_data.analysis_result is not None:
                    requirement.analysis_result = update_data.analysis_result

                if update_data.metadata is not None:
                    # 合并元数据
                    current_metadata = requirement.metadata or {}
                    current_metadata.update(update_data.metadata)
                    requirement.metadata = current_metadata

                await session.commit()

                logger.info(f"需求更新成功: {requirement_id}")
                return True

        except Exception as e:
            logger.error(f"更新需求失败: {requirement_id}，错误: {str(e)}")
            return False

    async def delete_requirement(self, requirement_id: str) -> bool:
        """
        删除需求

        Args:
            requirement_id: 需求ID

        Returns:
            是否成功
        """
        try:
            async with get_async_session() as session:
                requirement = await session.get(RequirementModel, requirement_id)
                if not requirement:
                    return False

                # 如果有关联的文档，从知识库删除
                if requirement.metadata and requirement.metadata.get("document_id"):
                    try:
                        document_id = requirement.metadata["document_id"]
                        await self.knowledge_service.delete_document(document_id)
                    except Exception as e:
                        logger.warning(f"删除关联文档失败: {str(e)}")

                # 删除需求
                await session.delete(requirement)
                await session.commit()

                logger.info(f"需求删除成功: {requirement_id}")
                return True

        except Exception as e:
            logger.error(f"删除需求失败: {requirement_id}，错误: {str(e)}")
            return False

    async def analyze_with_llm(
        self,
        requirement_id: str,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        使用LLM分析需求

        Args:
            requirement_id: 需求ID
            system_prompt: 系统提示

        Returns:
            分析结果
        """
        try:
            async with get_async_session() as session:
                requirement = await session.get(RequirementModel, requirement_id)
                if not requirement:
                    raise ValueError(f"需求不存在: {requirement_id}")

                # 准备提示
                if system_prompt is None:
                    system_prompt = """
                    你是一个需求分析专家。请分析以下需求并提供结构化分析结果。
                    包括：核心目标、主要功能、技术约束、假设条件、建议技术栈等。
                    请以JSON格式返回。
                    """

                user_prompt = f"""
                需求标题: {requirement.title}

                需求描述: {requirement.description or '无'}

                请分析这个需求并提供结构化分析结果。
                """

                # 如果有相关文档，添加到提示中
                if requirement.metadata and requirement.metadata.get("document_id"):
                    try:
                        # 检索相关文档内容
                        from models.schemas import KnowledgeRetrievalRequest
                        retrieval_request = KnowledgeRetrievalRequest(
                            query=requirement.title,
                            n_results=3,
                            use_hybrid=True
                        )

                        knowledge_response = await self.knowledge_service.retrieve_knowledge(
                            retrieval_request
                        )

                        if knowledge_response.results:
                            user_prompt += "\n\n相关文档内容:\n"
                            for i, result in enumerate(knowledge_response.results):
                                user_prompt += f"\n[{i+1}] {result.text[:300]}...\n"

                    except Exception as e:
                        logger.warning(f"检索相关文档失败: {str(e)}")

                # 调用LLM
                analysis_result = await self.llm_client.generate_json(
                    prompt=user_prompt,
                    system_prompt=system_prompt
                )

                # 更新需求
                requirement.analysis_result = analysis_result
                requirement.status = "analyzed"
                await session.commit()

                logger.info(f"LLM需求分析完成: {requirement_id}")
                return analysis_result

        except Exception as e:
            logger.error(f"LLM需求分析失败: {requirement_id}，错误: {str(e)}")
            raise