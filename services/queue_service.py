"""队列服务

提供任务队列的高级接口，集成业务逻辑。
"""

import asyncio
import loguru
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from core.queue.task_queue import (
    TaskQueueManager,
    TaskPriority,
    TaskType,
    TaskStatus,
)
from models.database import (
    get_async_session,
    Task as TaskModel,
    Requirement as RequirementModel,
    TaskExecution as TaskExecutionModel,
)
from config.settings import settings

logger = loguru.logger


class QueueService:
    """队列服务"""

    def __init__(self):
        """初始化队列服务"""
        self.task_queue = TaskQueueManager()

    async def initialize(self):
        """初始化服务"""
        await self.task_queue.connect()

    async def shutdown(self):
        """关闭服务"""
        await self.task_queue.close()

    async def submit_requirement_analysis(
        self,
        requirement_id: str,
        priority: TaskPriority = TaskPriority.HIGH,
        delay_seconds: int = 0
    ) -> str:
        """
        提交需求分析任务

        Args:
            requirement_id: 需求ID
            priority: 任务优先级
            delay_seconds: 延迟执行时间（秒）

        Returns:
            任务ID
        """
        try:
            # 验证需求存在
            async with get_async_session() as session:
                requirement = await session.get(RequirementModel, requirement_id)
                if not requirement:
                    raise ValueError(f"需求不存在: {requirement_id}")

                # 更新需求状态
                requirement.status = 'pending'
                requirement.updated_at = datetime.utcnow()
                await session.commit()

            # 提交任务到队列
            task_id = await self.task_queue.enqueue_task(
                task_type=TaskType.REQUIREMENT_ANALYSIS,
                data={"requirement_id": requirement_id},
                priority=priority,
                delay_seconds=delay_seconds,
                metadata={
                    "requirement_id": requirement_id,
                    "action": "analysis",
                    "submitted_at": datetime.utcnow().isoformat(),
                }
            )

            logger.info(f"需求分析任务已提交: {requirement_id} -> 任务ID: {task_id}")
            return task_id

        except Exception as e:
            logger.error(f"提交需求分析任务失败: {e}")
            raise

    async def submit_task_execution(
        self,
        task_id: str,
        agent_type: str = "development",
        priority: TaskPriority = TaskPriority.STANDARD
    ) -> str:
        """
        提交任务执行

        Args:
            task_id: 任务ID
            agent_type: 智能体类型
            priority: 任务优先级

        Returns:
            任务ID
        """
        try:
            # 验证任务存在
            async with get_async_session() as session:
                task = await session.get(TaskModel, task_id)
                if not task:
                    raise ValueError(f"任务不存在: {task_id}")

                # 检查任务是否可执行
                if task.status not in ['pending', 'blocked']:
                    raise ValueError(f"任务状态不可执行: {task.status}")

                # 检查依赖任务是否完成
                if task.dependencies:
                    pending_deps = [dep for dep in task.dependencies if dep.status != 'completed']
                    if pending_deps:
                        raise ValueError(f"任务依赖未完成: {len(pending_deps)} 个依赖任务待完成")

                # 更新任务状态
                task.status = 'queued'
                task.updated_at = datetime.utcnow()
                await session.commit()

            # 根据任务类型确定工作流类型
            task_type_mapping = {
                "development": TaskType.DEVELOPMENT,
                "review": TaskType.REVIEW,
                "test": TaskType.TEST,
            }

            workflow_type = task_type_mapping.get(task.task_type, TaskType.WORKFLOW)

            # 提交任务到队列
            queue_task_id = await self.task_queue.enqueue_task(
                task_type=workflow_type,
                data={
                    "task_id": task_id,
                    "agent_type": agent_type,
                    "task_type": task.task_type,
                },
                priority=priority,
                metadata={
                    "task_id": task_id,
                    "project_id": task.project_id,
                    "task_type": task.task_type,
                    "agent_type": agent_type,
                    "submitted_at": datetime.utcnow().isoformat(),
                }
            )

            logger.info(f"任务执行已提交: {task_id} ({task.task_type}) -> 队列任务ID: {queue_task_id}")
            return queue_task_id

        except Exception as e:
            logger.error(f"提交任务执行失败: {e}")
            raise

    async def submit_workflow_execution(
        self,
        workflow_type: str,
        workflow_data: Dict[str, Any],
        priority: TaskPriority = TaskPriority.STANDARD,
        delay_seconds: int = 0
    ) -> str:
        """
        提交工作流执行

        Args:
            workflow_type: 工作流类型
            workflow_data: 工作流数据
            priority: 任务优先级
            delay_seconds: 延迟执行时间（秒）

        Returns:
            任务ID
        """
        try:
            task_id = await self.task_queue.enqueue_task(
                task_type=TaskType.WORKFLOW,
                data={
                    "workflow_type": workflow_type,
                    **workflow_data,
                },
                priority=priority,
                delay_seconds=delay_seconds,
                metadata={
                    "workflow_type": workflow_type,
                    "data": workflow_data,
                    "submitted_at": datetime.utcnow().isoformat(),
                }
            )

            logger.info(f"工作流执行已提交: {workflow_type} -> 任务ID: {task_id}")
            return task_id

        except Exception as e:
            logger.error(f"提交工作流执行失败: {e}")
            raise

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            任务状态信息
        """
        try:
            # 首先从队列获取状态
            queue_status = await self.task_queue.get_task_status(task_id)
            if queue_status:
                return {
                    "source": "queue",
                    **queue_status,
                }

            # 如果队列中没有，尝试从数据库获取
            async with get_async_session() as session:
                # 检查是否是数据库任务ID
                task = await session.get(TaskModel, task_id)
                if task:
                    return {
                        "source": "database",
                        "id": task_id,
                        "type": "task_execution",
                        "status": task.status,
                        "created_at": task.created_at.isoformat() if task.created_at else None,
                        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
                    }

                # 检查是否是执行记录ID
                execution = await session.get(TaskExecutionModel, task_id)
                if execution:
                    return {
                        "source": "database",
                        "id": task_id,
                        "type": "task_execution_record",
                        "status": execution.status,
                        "created_at": execution.started_at.isoformat() if execution.started_at else None,
                        "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                    }

            return None

        except Exception as e:
            logger.error(f"获取任务状态失败: {e}")
            return None

    async def cancel_task(self, task_id: str) -> bool:
        """
        取消任务

        Args:
            task_id: 任务ID

        Returns:
            是否成功
        """
        try:
            # 尝试从队列取消
            cancelled = await self.task_queue.cancel_task(task_id)
            if cancelled:
                return True

            # 如果队列中没有，尝试更新数据库任务状态
            async with get_async_session() as session:
                task = await session.get(TaskModel, task_id)
                if task:
                    task.status = 'cancelled'
                    task.updated_at = datetime.utcnow()
                    await session.commit()
                    return True

            return False

        except Exception as e:
            logger.error(f"取消任务失败: {e}")
            return False

    async def get_queue_stats(self) -> Dict[str, Any]:
        """
        获取队列统计信息

        Returns:
            队列统计信息
        """
        try:
            queue_stats = await self.task_queue.get_queue_stats()

            # 获取数据库中的任务统计
            async with get_async_session() as session:
                from sqlalchemy import select, func

                # 任务状态统计
                stmt = select(
                    TaskModel.status,
                    func.count(TaskModel.id).label('count')
                ).group_by(TaskModel.status)

                result = await session.execute(stmt)
                db_task_stats = {row[0]: row[1] for row in result}

                # 执行记录统计
                stmt = select(
                    TaskExecutionModel.status,
                    func.count(TaskExecutionModel.id).label('count')
                ).group_by(TaskExecutionModel.status)

                result = await session.execute(stmt)
                db_execution_stats = {row[0]: row[1] for row in result}

            return {
                "queue_stats": queue_stats,
                "database_stats": {
                    "tasks": db_task_stats,
                    "executions": db_execution_stats,
                },
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"获取队列统计失败: {e}")
            return {"error": str(e)}

    async def retry_failed_tasks(
        self,
        max_retries: int = 3,
        older_than_minutes: int = 30
    ) -> Dict[str, Any]:
        """
        重试失败的任务

        Args:
            max_retries: 最大重试次数
            older_than_minutes: 只重试多少分钟前的失败任务

        Returns:
            重试结果
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(minutes=older_than_minutes)

            async with get_async_session() as session:
                from sqlalchemy import select

                # 查找失败的任务
                stmt = select(TaskModel).where(
                    TaskModel.status == 'failed',
                    TaskModel.updated_at < cutoff_time
                ).limit(100)  # 限制每次重试数量

                result = await session.execute(stmt)
                failed_tasks = result.scalars().all()

                retried_count = 0
                for task in failed_tasks:
                    try:
                        # 检查重试次数
                        metadata = task.metadata or {}
                        retry_count = metadata.get('retry_count', 0)
                        if retry_count >= max_retries:
                            continue

                        # 提交重试
                        await self.submit_task_execution(
                            task_id=task.id,
                            agent_type=task.task_type,
                            priority=TaskPriority.STANDARD
                        )

                        # 更新重试计数
                        metadata['retry_count'] = retry_count + 1
                        metadata['last_retry_at'] = datetime.utcnow().isoformat()
                        task.metadata = metadata
                        task.updated_at = datetime.utcnow()

                        retried_count += 1

                    except Exception as task_error:
                        logger.error(f"重试任务失败 {task.id}: {task_error}")

                await session.commit()

            logger.info(f"重试失败任务完成: {retried_count} 个任务已重试")
            return {
                "retried_count": retried_count,
                "total_failed": len(failed_tasks),
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"重试失败任务失败: {e}")
            return {"error": str(e)}

    async def monitor_and_cleanup(self):
        """监控和清理任务"""
        try:
            # 清理已完成的任务
            cleaned_count = await self.task_queue.cleanup_completed_tasks()

            # 重试失败的任务
            retry_result = await self.retry_failed_tasks()

            # 获取当前统计
            stats = await self.get_queue_stats()

            return {
                "cleaned_tasks": cleaned_count,
                "retry_result": retry_result,
                "current_stats": stats,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"监控和清理失败: {e}")
            return {"error": str(e)}

    async def submit_batch_tasks(
        self,
        tasks_data: List[Dict[str, Any]],
        priority: TaskPriority = TaskPriority.STANDARD
    ) -> List[str]:
        """
        批量提交任务

        Args:
            tasks_data: 任务数据列表
            priority: 任务优先级

        Returns:
            任务ID列表
        """
        task_ids = []
        for task_data in tasks_data:
            try:
                task_type = task_data.get("type")
                data = task_data.get("data", {})

                if task_type == "requirement_analysis":
                    task_id = await self.submit_requirement_analysis(
                        requirement_id=data.get("requirement_id"),
                        priority=priority
                    )
                elif task_type == "task_execution":
                    task_id = await self.submit_task_execution(
                        task_id=data.get("task_id"),
                        agent_type=data.get("agent_type", "development"),
                        priority=priority
                    )
                else:
                    task_id = await self.submit_workflow_execution(
                        workflow_type=task_type,
                        workflow_data=data,
                        priority=priority
                    )

                task_ids.append(task_id)

            except Exception as e:
                logger.error(f"批量提交任务失败: {e}")

        logger.info(f"批量提交任务完成: {len(task_ids)}/{len(tasks_data)} 个任务成功")
        return task_ids