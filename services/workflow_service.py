"""工作流服务

提供工作流管理和执行的高级接口。
"""

import asyncio
import uuid
import loguru
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from core.workflow.workflow_manager import (
    WorkflowManager,
    WorkflowType,
    WorkflowStatus,
    get_workflow_manager,
)
from core.agents.agent_orchestrator import get_agent_orchestrator
from models.database import (
    get_async_session,
    Task as TaskModel,
    Requirement as RequirementModel,
    WorkflowExecution as WorkflowExecutionModel,
    WorkflowState as WorkflowStateModel,
)
from services.queue_service import QueueService
from services.task_service import TaskService

logger = loguru.logger


class WorkflowService:
    """工作流服务"""

    def __init__(self):
        """初始化工作流服务"""
        self.workflow_manager = None
        self.agent_orchestrator = None
        self.queue_service = None
        self.task_service = None

    async def initialize(self):
        """初始化服务"""
        if self.workflow_manager is None:
            self.workflow_manager = await get_workflow_manager()

        if self.agent_orchestrator is None:
            self.agent_orchestrator = await get_agent_orchestrator()

        if self.queue_service is None:
            self.queue_service = QueueService()
            await self.queue_service.initialize()

        if self.task_service is None:
            self.task_service = TaskService()

        logger.info("工作流服务初始化完成")

    async def shutdown(self):
        """关闭服务"""
        if self.queue_service:
            await self.queue_service.shutdown()

    async def execute_development_workflow(
        self,
        task_id: str,
        input_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行开发工作流

        Args:
            task_id: 任务ID
            input_data: 输入数据

        Returns:
            工作流执行结果
        """
        try:
            await self.initialize()

            # 获取任务信息
            async with get_async_session() as session:
                task = await session.get(TaskModel, task_id)
                if not task:
                    raise ValueError(f"任务不存在: {task_id}")

                # 准备输入数据
                if input_data is None:
                    input_data = {
                        "task_id": task_id,
                        "task_description": task.description or task.title,
                        "project_id": task.project_id,
                        "requirement_id": task.requirement_id,
                        "technical_requirements": task.metadata.get("technical_requirements", {}),
                        "code_context": task.metadata.get("code_context", ""),
                    }

                # 更新任务状态
                task.status = 'in_progress'
                task.started_at = datetime.utcnow()
                await session.commit()

            # 执行开发工作流
            workflow_id = f"dev_{task_id}_{uuid.uuid4().hex[:8]}"
            result = await self.workflow_manager.execute_workflow(
                workflow_type=WorkflowType.DEVELOPMENT,
                input_data=input_data,
                workflow_id=workflow_id,
                config={
                    "task_id": task_id,
                    "priority": "standard",
                    "timeout": 1800,  # 30分钟
                }
            )

            # 更新任务状态
            await self._update_task_from_workflow_result(task_id, result)

            logger.info(f"开发工作流执行完成: {workflow_id} ({task_id})")
            return result

        except Exception as e:
            logger.error(f"开发工作流执行失败: {e}")

            # 更新任务状态为失败
            async with get_async_session() as session:
                task = await session.get(TaskModel, task_id)
                if task:
                    task.status = 'failed'
                    task.updated_at = datetime.utcnow()
                    await session.commit()

            raise

    async def execute_review_workflow(
        self,
        task_id: str,
        code_artifacts: Dict[str, Any],
        input_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行评审工作流

        Args:
            task_id: 任务ID
            code_artifacts: 代码工件
            input_data: 输入数据

        Returns:
            工作流执行结果
        """
        try:
            await self.initialize()

            # 获取任务信息
            async with get_async_session() as session:
                task = await session.get(TaskModel, task_id)
                if not task:
                    raise ValueError(f"任务不存在: {task_id}")

                # 准备输入数据
                if input_data is None:
                    input_data = {
                        "task_id": task_id,
                        "code": code_artifacts,
                        "code_metadata": {
                            "task_id": task_id,
                            "project_id": task.project_id,
                            "language": code_artifacts.get("language", "unknown"),
                        },
                    }

                # 更新任务状态
                task.status = 'in_progress'
                task.started_at = datetime.utcnow()
                await session.commit()

            # 执行评审工作流
            workflow_id = f"review_{task_id}_{uuid.uuid4().hex[:8]}"
            result = await self.workflow_manager.execute_workflow(
                workflow_type=WorkflowType.REVIEW,
                input_data=input_data,
                workflow_id=workflow_id,
                config={
                    "task_id": task_id,
                    "check_security": True,
                    "check_performance": True,
                }
            )

            # 更新任务状态
            await self._update_task_from_workflow_result(task_id, result)

            logger.info(f"评审工作流执行完成: {workflow_id} ({task_id})")
            return result

        except Exception as e:
            logger.error(f"评审工作流执行失败: {e}")

            # 更新任务状态为失败
            async with get_async_session() as session:
                task = await session.get(TaskModel, task_id)
                if task:
                    task.status = 'failed'
                    task.updated_at = datetime.utcnow()
                    await session.commit()

            raise

    async def execute_test_workflow(
        self,
        task_id: str,
        code_artifacts: Dict[str, Any],
        input_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行测试工作流

        Args:
            task_id: 任务ID
            code_artifacts: 代码工件
            input_data: 输入数据

        Returns:
            工作流执行结果
        """
        try:
            await self.initialize()

            # 获取任务信息
            async with get_async_session() as session:
                task = await session.get(TaskModel, task_id)
                if not task:
                    raise ValueError(f"任务不存在: {task_id}")

                # 准备输入数据
                if input_data is None:
                    input_data = {
                        "task_id": task_id,
                        "code": code_artifacts,
                        "function_description": task.description or task.title,
                        "test_requirements": task.metadata.get("test_requirements", [
                            "unit_tests",
                            "boundary_tests",
                            "exception_tests",
                        ]),
                    }

                # 更新任务状态
                task.status = 'in_progress'
                task.started_at = datetime.utcnow()
                await session.commit()

            # 执行测试工作流
            workflow_id = f"test_{task_id}_{uuid.uuid4().hex[:8]}"
            result = await self.workflow_manager.execute_workflow(
                workflow_type=WorkflowType.TEST,
                input_data=input_data,
                workflow_id=workflow_id,
                config={
                    "task_id": task_id,
                    "test_framework": "pytest",
                    "min_coverage": 80,
                }
            )

            # 更新任务状态
            await self._update_task_from_workflow_result(task_id, result)

            logger.info(f"测试工作流执行完成: {workflow_id} ({task_id})")
            return result

        except Exception as e:
            logger.error(f"测试工作流执行失败: {e}")

            # 更新任务状态为失败
            async with get_async_session() as session:
                task = await session.get(TaskModel, task_id)
                if task:
                    task.status = 'failed'
                    task.updated_at = datetime.utcnow()
                    await session.commit()

            raise

    async def execute_full_development_workflow(
        self,
        requirement_id: str,
        input_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行完整开发工作流（需求分析 → 任务规划 → 开发 → 评审 → 测试）

        Args:
            requirement_id: 需求ID
            input_data: 输入数据

        Returns:
            工作流执行结果
        """
        try:
            await self.initialize()

            # 获取需求信息
            async with get_async_session() as session:
                requirement = await session.get(RequirementModel, requirement_id)
                if not requirement:
                    raise ValueError(f"需求不存在: {requirement_id}")

                # 准备输入数据
                if input_data is None:
                    input_data = {
                        "requirement_id": requirement_id,
                        "requirement_data": {
                            "document_content": requirement.description or "",
                            "document_path": requirement.document_path,
                        },
                        "project_context": {
                            "project_id": requirement.project_id,
                            "project_name": "",  # 可以从项目表查询
                            "tech_stack": requirement.analysis_result.get("suggested_tech_stack", []),
                        },
                    }

                # 更新需求状态
                requirement.status = 'processing'
                requirement.updated_at = datetime.utcnow()
                await session.commit()

            # 执行完整开发工作流
            workflow_id = f"full_dev_{requirement_id}_{uuid.uuid4().hex[:8]}"
            result = await self.workflow_manager.execute_workflow(
                workflow_type=WorkflowType.FULL_DEVELOPMENT,
                input_data=input_data,
                workflow_id=workflow_id,
                config={
                    "requirement_id": requirement_id,
                    "timeout": 3600,  # 1小时
                    "enable_review": True,
                    "enable_testing": True,
                }
            )

            # 更新需求状态
            await self._update_requirement_from_workflow_result(requirement_id, result)

            logger.info(f"完整开发工作流执行完成: {workflow_id} ({requirement_id})")
            return result

        except Exception as e:
            logger.error(f"完整开发工作流执行失败: {e}")

            # 更新需求状态为失败
            async with get_async_session() as session:
                requirement = await session.get(RequirementModel, requirement_id)
                if requirement:
                    requirement.status = 'failed'
                    requirement.updated_at = datetime.utcnow()
                    await session.commit()

            raise

    async def get_workflow_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """
        获取工作流状态

        Args:
            workflow_id: 工作流ID

        Returns:
            工作流状态信息
        """
        try:
            await self.initialize()
            return await self.workflow_manager.get_workflow_status(workflow_id)
        except Exception as e:
            logger.error(f"获取工作流状态失败: {e}")
            return None

    async def pause_workflow(self, workflow_id: str) -> bool:
        """
        暂停工作流

        Args:
            workflow_id: 工作流ID

        Returns:
            是否成功
        """
        try:
            await self.initialize()
            return await self.workflow_manager.pause_workflow(workflow_id)
        except Exception as e:
            logger.error(f"暂停工作流失败: {e}")
            return False

    async def resume_workflow(self, workflow_id: str) -> bool:
        """
        恢复工作流

        Args:
            workflow_id: 工作流ID

        Returns:
            是否成功
        """
        try:
            await self.initialize()
            return await self.workflow_manager.resume_workflow(workflow_id)
        except Exception as e:
            logger.error(f"恢复工作流失败: {e}")
            return False

    async def cancel_workflow(self, workflow_id: str) -> bool:
        """
        取消工作流

        Args:
            workflow_id: 工作流ID

        Returns:
            是否成功
        """
        try:
            await self.initialize()
            return await self.workflow_manager.cancel_workflow(workflow_id)
        except Exception as e:
            logger.error(f"取消工作流失败: {e}")
            return False

    async def get_workflow_history(self, workflow_id: str) -> List[Dict[str, Any]]:
        """
        获取工作流执行历史

        Args:
            workflow_id: 工作流ID

        Returns:
            执行历史列表
        """
        try:
            await self.initialize()
            return await self.workflow_manager.get_workflow_history(workflow_id)
        except Exception as e:
            logger.error(f"获取工作流历史失败: {e}")
            return []

    async def submit_workflow_via_queue(
        self,
        workflow_type: str,
        input_data: Dict[str, Any],
        priority: str = "standard"
    ) -> str:
        """
        通过队列提交工作流

        Args:
            workflow_type: 工作流类型
            input_data: 输入数据
            priority: 优先级

        Returns:
            队列任务ID
        """
        try:
            await self.initialize()

            # 提交到队列
            task_id = await self.queue_service.submit_workflow_execution(
                workflow_type=workflow_type,
                workflow_data=input_data,
                priority=priority
            )

            logger.info(f"工作流已提交到队列: {workflow_type} -> {task_id}")
            return task_id

        except Exception as e:
            logger.error(f"提交工作流到队列失败: {e}")
            raise

    async def _update_task_from_workflow_result(self, task_id: str, workflow_result: Dict[str, Any]):
        """
        根据工作流结果更新任务状态

        Args:
            task_id: 任务ID
            workflow_result: 工作流结果
        """
        try:
            async with get_async_session() as session:
                task = await session.get(TaskModel, task_id)
                if not task:
                    return

                # 更新任务状态
                if workflow_result.get("status") == "completed":
                    task.status = 'completed'
                    task.completed_at = datetime.utcnow()

                    # 保存工作流结果到元数据
                    metadata = task.metadata or {}
                    metadata["workflow_result"] = workflow_result
                    task.metadata = metadata
                elif workflow_result.get("status") == "failed":
                    task.status = 'failed'

                task.updated_at = datetime.utcnow()
                await session.commit()

        except Exception as e:
            logger.error(f"更新任务状态失败: {e}")

    async def _update_requirement_from_workflow_result(self, requirement_id: str, workflow_result: Dict[str, Any]):
        """
        根据工作流结果更新需求状态

        Args:
            requirement_id: 需求ID
            workflow_result: 工作流结果
        """
        try:
            async with get_async_session() as session:
                requirement = await session.get(RequirementModel, requirement_id)
                if not requirement:
                    return

                # 更新需求状态
                if workflow_result.get("status") == "completed":
                    requirement.status = 'completed'

                    # 保存工作流结果到分析结果
                    if "result" in workflow_result:
                        analysis_result = requirement.analysis_result or {}
                        analysis_result["workflow_execution"] = workflow_result["result"]
                        requirement.analysis_result = analysis_result
                elif workflow_result.get("status") == "failed":
                    requirement.status = 'failed'

                requirement.updated_at = datetime.utcnow()
                await session.commit()

        except Exception as e:
            logger.error(f"更新需求状态失败: {e}")

    async def monitor_workflows(self) -> Dict[str, Any]:
        """
        监控工作流状态

        Returns:
            监控结果
        """
        try:
            await self.initialize()

            async with get_async_session() as session:
                from sqlalchemy import select, func

                # 统计工作流状态
                stmt = select(
                    WorkflowExecutionModel.status,
                    func.count(WorkflowExecutionModel.id).label('count')
                ).group_by(WorkflowExecutionModel.status)

                result = await session.execute(stmt)
                status_stats = {row[0]: row[1] for row in result}

                # 统计最近24小时的工作流
                start_time = datetime.utcnow() - timedelta(hours=24)
                stmt = select(func.count(WorkflowExecutionModel.id)).where(
                    WorkflowExecutionModel.created_at >= start_time
                )
                result = await session.execute(stmt)
                recent_count = result.scalar() or 0

                # 计算成功率
                total = sum(status_stats.values())
                success_count = status_stats.get('completed', 0)
                success_rate = (success_count / total * 100) if total > 0 else 0

                # 获取最近失败的工作流
                stmt = select(WorkflowExecutionModel).where(
                    WorkflowExecutionModel.status == 'failed'
                ).order_by(WorkflowExecutionModel.created_at.desc()).limit(5)

                result = await session.execute(stmt)
                recent_failures = result.scalars().all()

                failures_info = []
                for failure in recent_failures:
                    failures_info.append({
                        "workflow_id": failure.workflow_id,
                        "workflow_type": failure.workflow_type,
                        "error_message": failure.error_message,
                        "created_at": failure.created_at.isoformat(),
                    })

            return {
                "status_stats": status_stats,
                "total_workflows": total,
                "recent_24h": recent_count,
                "success_rate": round(success_rate, 2),
                "recent_failures": failures_info,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"监控工作流失败: {e}")
            return {"error": str(e)}

    async def cleanup_old_workflows(self, days: int = 30):
        """
        清理旧的工作流记录

        Args:
            days: 清理多少天前的记录
        """
        try:
            await self.initialize()
            return await self.workflow_manager.cleanup_old_workflows(days)
        except Exception as e:
            logger.error(f"清理旧工作流记录失败: {e}")
            return 0

# 全局工作流服务实例
_workflow_service = None

async def get_workflow_service() -> WorkflowService:
    """
    获取工作流服务实例（单例模式）

    Returns:
        工作流服务实例
    """
    global _workflow_service
    if _workflow_service is None:
        _workflow_service = WorkflowService()
        await _workflow_service.initialize()
    return _workflow_service