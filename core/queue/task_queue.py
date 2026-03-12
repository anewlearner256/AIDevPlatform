"""任务队列管理器

管理任务队列的入队、出队、状态跟踪等功能。
"""

import json
import asyncio
import loguru
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List, Union
from uuid import uuid4

from redis.asyncio import Redis
from config.settings import settings
from tasks.celery_tasks import (
    process_requirement_analysis,
    task_planning_task,
    execute_high_priority_workflow,
    execute_standard_workflow,
    execute_background_workflow,
)

logger = loguru.logger


class TaskPriority(Enum):
    """任务优先级"""
    HIGH = "high"
    STANDARD = "standard"
    LOW = "low"
    BACKGROUND = "background"


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class TaskType(Enum):
    """任务类型"""
    REQUIREMENT_ANALYSIS = "requirement_analysis"
    TASK_PLANNING = "task_planning"
    DEVELOPMENT = "development"
    REVIEW = "review"
    TEST = "test"
    WORKFLOW = "workflow"
    MAINTENANCE = "maintenance"


class TaskQueueManager:
    """任务队列管理器"""

    def __init__(self, redis_client: Optional[Redis] = None):
        """
        初始化任务队列管理器

        Args:
            redis_client: Redis客户端实例
        """
        self.redis_client = redis_client
        self.prefix = "task_queue"

    async def connect(self):
        """连接到Redis"""
        if self.redis_client is None:
            self.redis_client = Redis.from_url(
                str(settings.redis_url),
                decode_responses=True,
                max_connections=10
            )

    async def close(self):
        """关闭Redis连接"""
        if self.redis_client:
            await self.redis_client.aclose()

    async def enqueue_task(
        self,
        task_type: Union[str, TaskType],
        data: Dict[str, Any],
        priority: Union[str, TaskPriority] = TaskPriority.STANDARD,
        delay_seconds: int = 0,
        retry_count: int = 3,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        将任务加入队列

        Args:
            task_type: 任务类型
            data: 任务数据
            priority: 任务优先级
            delay_seconds: 延迟执行时间（秒）
            retry_count: 重试次数
            metadata: 任务元数据

        Returns:
            任务ID
        """
        await self.connect()

        # 生成任务ID
        task_id = str(uuid4())

        # 准备任务数据
        task_data = {
            "id": task_id,
            "type": task_type.value if isinstance(task_type, TaskType) else task_type,
            "data": data,
            "priority": priority.value if isinstance(priority, TaskPriority) else priority,
            "status": TaskStatus.QUEUED.value,
            "created_at": datetime.utcnow().isoformat(),
            "delay_seconds": delay_seconds,
            "retry_count": retry_count,
            "retries_left": retry_count,
            "metadata": metadata or {},
            "attempts": 0,
        }

        # 存储任务数据
        task_key = f"{self.prefix}:tasks:{task_id}"
        await self.redis_client.set(task_key, json.dumps(task_data))

        # 根据优先级加入队列
        queue_name = self._get_queue_name(priority)
        if delay_seconds > 0:
            # 延迟任务
            delay_timestamp = datetime.utcnow().timestamp() + delay_seconds
            await self.redis_client.zadd(
                f"{self.prefix}:delayed:{queue_name}",
                {task_id: delay_timestamp}
            )
        else:
            # 立即执行任务
            await self.redis_client.rpush(queue_name, task_id)

        # 触发任务执行
        await self._trigger_task_execution(task_id, task_data)

        logger.info(f"任务入队: {task_id} ({task_type}, {priority})")
        return task_id

    async def dequeue_task(self, queue_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        从队列中取出任务

        Args:
            queue_name: 队列名称，如果为None则从最高优先级队列开始查找

        Returns:
            任务数据或None
        """
        await self.connect()

        if queue_name:
            # 从指定队列取出任务
            task_id = await self.redis_client.lpop(queue_name)
            if task_id:
                return await self._get_task_data(task_id)
        else:
            # 按优先级顺序从队列取出任务
            for priority in [TaskPriority.HIGH, TaskPriority.STANDARD, TaskPriority.LOW]:
                queue_name = self._get_queue_name(priority)
                task_id = await self.redis_client.lpop(queue_name)
                if task_id:
                    return await self._get_task_data(task_id)

        # 检查延迟任务
        await self._process_delayed_tasks()
        return None

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            任务状态信息或None
        """
        await self.connect()

        task_key = f"{self.prefix}:tasks:{task_id}"
        task_data = await self.redis_client.get(task_key)
        if not task_data:
            return None

        task_data = json.loads(task_data)
        return {
            "id": task_data["id"],
            "type": task_data["type"],
            "status": task_data["status"],
            "priority": task_data["priority"],
            "created_at": task_data["created_at"],
            "attempts": task_data.get("attempts", 0),
            "metadata": task_data.get("metadata", {}),
        }

    async def update_task_status(
        self,
        task_id: str,
        status: Union[str, TaskStatus],
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> bool:
        """
        更新任务状态

        Args:
            task_id: 任务ID
            status: 新状态
            result: 执行结果
            error: 错误信息

        Returns:
            是否成功
        """
        await self.connect()

        task_key = f"{self.prefix}:tasks:{task_id}"
        task_data = await self.redis_client.get(task_key)
        if not task_data:
            return False

        task_data = json.loads(task_data)
        task_data["status"] = status.value if isinstance(status, TaskStatus) else status
        task_data["updated_at"] = datetime.utcnow().isoformat()

        if result is not None:
            task_data["result"] = result
        if error is not None:
            task_data["error"] = error
            task_data["last_error_at"] = datetime.utcnow().isoformat()

        await self.redis_client.set(task_key, json.dumps(task_data))

        # 如果任务失败且还有重试次数，重新入队
        if (status == TaskStatus.FAILED.value or status == TaskStatus.FAILED) and task_data.get("retries_left", 0) > 0:
            await self._retry_task(task_id, task_data)

        logger.debug(f"任务状态更新: {task_id} -> {status}")
        return True

    async def cancel_task(self, task_id: str) -> bool:
        """
        取消任务

        Args:
            task_id: 任务ID

        Returns:
            是否成功
        """
        await self.connect()

        # 更新任务状态
        success = await self.update_task_status(task_id, TaskStatus.CANCELLED)
        if not success:
            return False

        # 从队列中移除任务
        task_key = f"{self.prefix}:tasks:{task_id}"
        task_data = await self.redis_client.get(task_key)
        if task_data:
            task_data = json.loads(task_data)
            queue_name = self._get_queue_name_from_priority(task_data["priority"])

            # 从主队列移除
            await self.redis_client.lrem(queue_name, 0, task_id)

            # 从延迟队列移除
            delayed_key = f"{self.prefix}:delayed:{queue_name}"
            await self.redis_client.zrem(delayed_key, task_id)

        logger.info(f"任务已取消: {task_id}")
        return True

    async def get_queue_stats(self) -> Dict[str, Any]:
        """
        获取队列统计信息

        Returns:
            队列统计信息
        """
        await self.connect()

        stats = {
            "queues": {},
            "total_tasks": 0,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # 统计各队列任务数量
        for priority in [TaskPriority.HIGH, TaskPriority.STANDARD, TaskPriority.LOW]:
            queue_name = self._get_queue_name(priority)
            queue_length = await self.redis_client.llen(queue_name)
            stats["queues"][priority.value] = queue_length
            stats["total_tasks"] += queue_length

        # 统计延迟任务
        for priority in [TaskPriority.HIGH, TaskPriority.STANDARD, TaskPriority.LOW]:
            delayed_key = f"{self.prefix}:delayed:{self._get_queue_name(priority)}"
            delayed_count = await self.redis_client.zcard(delayed_key)
            stats["queues"][f"{priority.value}_delayed"] = delayed_count
            stats["total_tasks"] += delayed_count

        # 统计运行中任务
        running_count = await self._count_running_tasks()
        stats["queues"]["running"] = running_count
        stats["total_tasks"] += running_count

        return stats

    async def cleanup_completed_tasks(self, older_than_hours: int = 24):
        """
        清理已完成的任务

        Args:
            older_than_hours: 清理多少小时前的任务
        """
        await self.connect()

        cutoff_time = datetime.utcnow().timestamp() - (older_than_hours * 3600)
        task_keys = await self.redis_client.keys(f"{self.prefix}:tasks:*")

        deleted_count = 0
        for task_key in task_keys:
            task_data = await self.redis_client.get(task_key)
            if task_data:
                task_data = json.loads(task_data)
                created_at = datetime.fromisoformat(task_data["created_at"]).timestamp()

                if (task_data["status"] in [TaskStatus.COMPLETED.value, TaskStatus.CANCELLED.value, TaskStatus.FAILED.value]
                        and created_at < cutoff_time):
                    await self.redis_client.delete(task_key)
                    deleted_count += 1

        logger.info(f"清理已完成任务: 删除了 {deleted_count} 个任务")
        return deleted_count

    def _get_queue_name(self, priority: Union[str, TaskPriority]) -> str:
        """获取队列名称"""
        priority_value = priority.value if isinstance(priority, TaskPriority) else priority
        return f"{self.prefix}:{priority_value}"

    def _get_queue_name_from_priority(self, priority: str) -> str:
        """从优先级获取队列名称"""
        return f"{self.prefix}:{priority}"

    async def _get_task_data(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务数据"""
        task_key = f"{self.prefix}:tasks:{task_id}"
        task_data = await self.redis_client.get(task_key)
        return json.loads(task_data) if task_data else None

    async def _trigger_task_execution(self, task_id: str, task_data: Dict[str, Any]):
        """触发任务执行"""
        task_type = task_data["type"]
        data = task_data["data"]

        try:
            # 更新任务状态为运行中
            await self.update_task_status(task_id, TaskStatus.RUNNING)

            # 根据任务类型调用相应的Celery任务
            if task_type == TaskType.REQUIREMENT_ANALYSIS.value:
                if "requirement_id" in data:
                    process_requirement_analysis.delay(data["requirement_id"])
                else:
                    raise ValueError("需求分析任务缺少requirement_id")

            elif task_type == TaskType.TASK_PLANNING.value:
                if "requirement_id" in data:
                    task_planning_task.delay(data["requirement_id"])
                else:
                    raise ValueError("任务规划任务缺少requirement_id")

            elif task_type == TaskType.DEVELOPMENT.value:
                if "task_id" in data:
                    execute_standard_workflow.delay(data["task_id"])
                else:
                    raise ValueError("开发任务缺少task_id")

            elif task_type == TaskType.WORKFLOW.value:
                workflow_type = data.get("workflow_type", "standard")
                if workflow_type == "high_priority" and "task_id" in data:
                    execute_high_priority_workflow.delay(data["task_id"])
                else:
                    execute_background_workflow.delay(workflow_type, data)

            else:
                logger.warning(f"未知的任务类型: {task_type}")
                await self.update_task_status(task_id, TaskStatus.FAILED, error=f"未知的任务类型: {task_type}")

        except Exception as e:
            logger.error(f"触发任务执行失败: {e}")
            await self.update_task_status(task_id, TaskStatus.FAILED, error=str(e))

    async def _process_delayed_tasks(self):
        """处理延迟任务"""
        current_time = datetime.utcnow().timestamp()

        for priority in [TaskPriority.HIGH, TaskPriority.STANDARD, TaskPriority.LOW]:
            queue_name = self._get_queue_name(priority)
            delayed_key = f"{self.prefix}:delayed:{queue_name}"

            # 获取到期的延迟任务
            expired_tasks = await self.redis_client.zrangebyscore(
                delayed_key, 0, current_time
            )

            for task_id in expired_tasks:
                # 从延迟队列移除
                await self.redis_client.zrem(delayed_key, task_id)

                # 加入主队列
                await self.redis_client.rpush(queue_name, task_id)

                logger.debug(f"延迟任务到期: {task_id}")

    async def _retry_task(self, task_id: str, task_data: Dict[str, Any]):
        """重试任务"""
        retries_left = task_data.get("retries_left", 0)
        if retries_left <= 0:
            return

        # 更新重试次数
        task_data["retries_left"] = retries_left - 1
        task_data["attempts"] = task_data.get("attempts", 0) + 1
        task_data["status"] = TaskStatus.RETRYING.value
        task_data["last_retry_at"] = datetime.utcnow().isoformat()

        task_key = f"{self.prefix}:tasks:{task_id}"
        await self.redis_client.set(task_key, json.dumps(task_data))

        # 重新加入队列（延迟重试）
        delay_seconds = 2 ** task_data["attempts"]  # 指数退避
        queue_name = self._get_queue_name_from_priority(task_data["priority"])
        delay_timestamp = datetime.utcnow().timestamp() + delay_seconds

        await self.redis_client.zadd(
            f"{self.prefix}:delayed:{queue_name}",
            {task_id: delay_timestamp}
        )

        logger.info(f"任务重试安排: {task_id} (延迟 {delay_seconds}秒, 剩余重试 {retries_left-1}次)")

    async def _count_running_tasks(self) -> int:
        """统计运行中任务数量"""
        task_keys = await self.redis_client.keys(f"{self.prefix}:tasks:*")
        running_count = 0

        for task_key in task_keys:
            task_data = await self.redis_client.get(task_key)
            if task_data:
                task_data = json.loads(task_data)
                if task_data.get("status") == TaskStatus.RUNNING.value:
                    running_count += 1

        return running_count