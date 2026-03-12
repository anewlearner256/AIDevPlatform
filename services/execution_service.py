"""执行服务

管理任务执行和结果处理。
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import loguru

from models.schemas import (
    TaskExecutionCreate,
    TaskExecutionUpdate,
    TaskExecutionResponse,
)
from models.database import get_async_session
from models.database import (
    TaskExecution as TaskExecutionModel,
    Task as TaskModel,
    ExecutionResult as ExecutionResultModel
)

logger = loguru.logger

class ExecutionService:
    """执行服务"""

    async def create_execution(
        self,
        execution_data: TaskExecutionCreate
    ) -> TaskExecutionResponse:
        """
        创建任务执行

        Args:
            execution_data: 执行数据

        Returns:
            执行响应
        """
        try:
            async with get_async_session() as session:
                # 验证任务存在
                task = await session.get(TaskModel, execution_data.task_id)
                if not task:
                    raise ValueError(f"任务不存在: {execution_data.task_id}")

                # 创建执行记录
                execution = TaskExecutionModel(
                    task_id=execution_data.task_id,
                    execution_type=execution_data.execution_type,
                    agent_type=execution_data.agent_type,
                    input_data=execution_data.input_data or {},
                    metadata=execution_data.metadata or {},
                )

                session.add(execution)
                await session.commit()
                await session.refresh(execution)

                # 转换为响应
                response = await self._execution_to_response(execution)

                logger.info(f"任务执行创建成功: {execution.id}，任务: {execution_data.task_id}")
                return response

        except Exception as e:
            logger.error(f"创建任务执行失败: {str(e)}")
            raise

    async def get_execution(self, execution_id: str) -> Optional[TaskExecutionResponse]:
        """
        获取任务执行

        Args:
            execution_id: 执行ID

        Returns:
            执行响应
        """
        try:
            async with get_async_session() as session:
                execution = await session.get(TaskExecutionModel, execution_id)
                if not execution:
                    return None

                # 转换为响应
                response = await self._execution_to_response(execution)
                return response

        except Exception as e:
            logger.error(f"获取任务执行失败: {execution_id}，错误: {str(e)}")
            raise

    async def update_execution(
        self,
        execution_id: str,
        update_data: TaskExecutionUpdate
    ) -> bool:
        """
        更新任务执行

        Args:
            execution_id: 执行ID
            update_data: 更新数据

        Returns:
            是否成功
        """
        try:
            async with get_async_session() as session:
                execution = await session.get(TaskExecutionModel, execution_id)
                if not execution:
                    return False

                # 更新字段
                if update_data.status is not None:
                    old_status = execution.status
                    new_status = update_data.status

                    execution.status = new_status

                    # 如果状态变为完成，设置完成时间
                    if new_status in ["completed", "failed", "cancelled"] and old_status not in ["completed", "failed", "cancelled"]:
                        execution.completed_at = update_data.completed_at or datetime.utcnow()

                        # 计算执行时间
                        if execution.started_at and execution.completed_at:
                            execution_time = (execution.completed_at - execution.started_at).total_seconds()
                            execution.execution_time = update_data.execution_time or execution_time

                if update_data.output_data is not None:
                    execution.output_data = update_data.output_data

                if update_data.error_message is not None:
                    execution.error_message = update_data.error_message

                if update_data.completed_at is not None:
                    execution.completed_at = update_data.completed_at

                if update_data.execution_time is not None:
                    execution.execution_time = update_data.execution_time

                if update_data.resource_usage is not None:
                    execution.resource_usage = update_data.resource_usage

                if update_data.metadata is not None:
                    # 合并元数据
                    current_metadata = execution.metadata or {}
                    current_metadata.update(update_data.metadata)
                    execution.metadata = current_metadata

                await session.commit()

                logger.info(f"任务执行更新成功: {execution_id}")
                return True

        except Exception as e:
            logger.error(f"更新任务执行失败: {execution_id}，错误: {str(e)}")
            return False

    async def delete_execution(self, execution_id: str) -> bool:
        """
        删除任务执行

        Args:
            execution_id: 执行ID

        Returns:
            是否成功
        """
        try:
            async with get_async_session() as session:
                execution = await session.get(TaskExecutionModel, execution_id)
                if not execution:
                    return False

                # 删除执行（级联删除由数据库处理）
                await session.delete(execution)
                await session.commit()

                logger.info(f"任务执行删除成功: {execution_id}")
                return True

        except Exception as e:
            logger.error(f"删除任务执行失败: {execution_id}，错误: {str(e)}")
            return False

    async def list_executions(
        self,
        task_id: Optional[str] = None,
        status: Optional[str] = None,
        agent_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[TaskExecutionResponse]:
        """
        列出任务执行

        Args:
            task_id: 任务ID过滤
            status: 状态过滤
            agent_type: 智能体类型过滤
            skip: 跳过数量
            limit: 返回数量

        Returns:
            执行列表
        """
        try:
            async with get_async_session() as session:
                from sqlalchemy import select

                # 构建查询
                query = select(TaskExecutionModel)

                # 应用过滤条件
                if task_id:
                    query = query.where(TaskExecutionModel.task_id == task_id)

                if status:
                    query = query.where(TaskExecutionModel.status == status)

                if agent_type:
                    query = query.where(TaskExecutionModel.agent_type == agent_type)

                # 计数
                from sqlalchemy.sql import func
                count_query = select(func.count()).select_from(TaskExecutionModel)

                if task_id:
                    count_query = count_query.where(TaskExecutionModel.task_id == task_id)

                if status:
                    count_query = count_query.where(TaskExecutionModel.status == status)

                if agent_type:
                    count_query = count_query.where(TaskExecutionModel.agent_type == agent_type)

                total = await session.scalar(count_query)

                # 分页和排序
                query = query.offset(skip).limit(limit)
                query = query.order_by(TaskExecutionModel.started_at.desc())

                # 执行查询
                result = await session.execute(query)
                executions = result.scalars().all()

                # 转换为响应
                responses = []
                for execution in executions:
                    response = await self._execution_to_response(execution)
                    responses.append(response)

                filter_str = self._format_filters(task_id, status, agent_type)
                logger.info(f"列出任务执行成功{filter_str}，总数: {total}")
                return responses

        except Exception as e:
            logger.error(f"列出任务执行失败: {str(e)}")
            raise

    async def create_execution_result(
        self,
        execution_id: str,
        output_data: Dict[str, Any],
        error_data: Optional[Dict[str, Any]] = None,
        exit_code: Optional[int] = None,
        resource_usage: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        创建执行结果

        Args:
            execution_id: 执行ID
            output_data: 输出数据
            error_data: 错误数据
            exit_code: 退出码
            resource_usage: 资源使用情况

        Returns:
            是否成功
        """
        try:
            async with get_async_session() as session:
                # 验证执行存在
                execution = await session.get(TaskExecutionModel, execution_id)
                if not execution:
                    return False

                # 创建结果记录
                result = ExecutionResultModel(
                    task_execution_id=execution_id,
                    execution_output=str(output_data) if isinstance(output_data, (dict, list)) else output_data,
                    execution_error=str(error_data) if error_data else None,
                    exit_code=exit_code,
                    resource_usage=resource_usage or {},
                    environment_snapshot={}  # 实际项目中应捕获环境快照
                )

                session.add(result)

                # 更新执行状态（如果尚未完成）
                if execution.status == "running":
                    execution.status = "completed" if not error_data else "failed"
                    execution.completed_at = datetime.utcnow()

                    # 计算执行时间
                    if execution.started_at and execution.completed_at:
                        execution.execution_time = (execution.completed_at - execution.started_at).total_seconds()

                    execution.output_data = output_data
                    if error_data:
                        execution.error_message = str(error_data)

                await session.commit()

                logger.info(f"创建执行结果成功: {execution_id}")
                return True

        except Exception as e:
            logger.error(f"创建执行结果失败: {execution_id}，错误: {str(e)}")
            return False

    async def get_execution_result(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        获取执行结果

        Args:
            execution_id: 执行ID

        Returns:
            执行结果
        """
        try:
            async with get_async_session() as session:
                from sqlalchemy import select

                query = select(ExecutionResultModel).where(
                    ExecutionResultModel.task_execution_id == execution_id
                ).order_by(ExecutionResultModel.created_at.desc())

                result = await session.execute(query)
                execution_result = result.scalar()

                if not execution_result:
                    return None

                return {
                    "id": execution_result.id,
                    "execution_id": execution_result.task_execution_id,
                    "output": execution_result.execution_output,
                    "error": execution_result.execution_error,
                    "exit_code": execution_result.exit_code,
                    "resource_usage": execution_result.resource_usage or {},
                    "environment_snapshot": execution_result.environment_snapshot or {},
                    "created_at": execution_result.created_at,
                }

        except Exception as e:
            logger.error(f"获取执行结果失败: {execution_id}，错误: {str(e)}")
            raise

    async def get_execution_statistics(
        self,
        task_id: Optional[str] = None,
        agent_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取执行统计信息

        Args:
            task_id: 任务ID过滤
            agent_type: 智能体类型过滤

        Returns:
            统计信息
        """
        try:
            async with get_async_session() as session:
                from sqlalchemy import select, func

                # 构建查询
                query = select(TaskExecutionModel)

                if task_id:
                    query = query.where(TaskExecutionModel.task_id == task_id)

                if agent_type:
                    query = query.where(TaskExecutionModel.agent_type == agent_type)

                # 执行查询
                result = await session.execute(query)
                executions = result.scalars().all()

                if not executions:
                    return {
                        "total_executions": 0,
                        "status_distribution": {},
                        "agent_type_distribution": {},
                        "avg_execution_time": 0,
                        "success_rate": 0,
                    }

                # 计算统计
                total_executions = len(executions)
                completed_executions = sum(1 for e in executions if e.status == "completed")
                failed_executions = sum(1 for e in executions if e.status == "failed")
                success_rate = completed_executions / total_executions if total_executions > 0 else 0

                status_distribution = {}
                agent_type_distribution = {}

                total_execution_time = 0
                valid_execution_times = 0

                for execution in executions:
                    # 状态分布
                    status_distribution[execution.status] = status_distribution.get(execution.status, 0) + 1

                    # 智能体类型分布
                    if execution.agent_type:
                        agent_type_distribution[execution.agent_type] = agent_type_distribution.get(execution.agent_type, 0) + 1

                    # 执行时间统计
                    if execution.execution_time:
                        total_execution_time += execution.execution_time
                        valid_execution_times += 1

                avg_execution_time = total_execution_time / valid_execution_times if valid_execution_times > 0 else 0

                statistics = {
                    "total_executions": total_executions,
                    "status_distribution": status_distribution,
                    "agent_type_distribution": agent_type_distribution,
                    "avg_execution_time": avg_execution_time,
                    "success_rate": success_rate,
                    "completed_count": completed_executions,
                    "failed_count": failed_executions,
                }

                if task_id:
                    statistics["task_id"] = task_id

                logger.info(f"获取执行统计成功，任务: {task_id or '所有'}，总数: {total_executions}")
                return statistics

        except Exception as e:
            logger.error(f"获取执行统计失败: {str(e)}")
            raise

    async def cancel_execution(self, execution_id: str) -> bool:
        """
        取消任务执行

        Args:
            execution_id: 执行ID

        Returns:
            是否成功
        """
        try:
            async with get_async_session() as session:
                execution = await session.get(TaskExecutionModel, execution_id)
                if not execution:
                    return False

                # 只能取消运行中的执行
                if execution.status != "running":
                    logger.warning(f"执行 {execution_id} 状态为 {execution.status}，无法取消")
                    return False

                # 更新状态
                execution.status = "cancelled"
                execution.completed_at = datetime.utcnow()

                if execution.started_at and execution.completed_at:
                    execution.execution_time = (execution.completed_at - execution.started_at).total_seconds()

                await session.commit()

                logger.info(f"任务执行取消成功: {execution_id}")
                return True

        except Exception as e:
            logger.error(f"取消任务执行失败: {execution_id}，错误: {str(e)}")
            return False

    async def _execution_to_response(
        self,
        execution: TaskExecutionModel
    ) -> TaskExecutionResponse:
        """将执行模型转换为响应"""
        response = TaskExecutionResponse(
            id=execution.id,
            task_id=execution.task_id,
            execution_type=execution.execution_type,
            status=execution.status,
            agent_type=execution.agent_type,
            input_data=execution.input_data or {},
            output_data=execution.output_data,
            error_message=execution.error_message,
            started_at=execution.started_at,
            completed_at=execution.completed_at,
            execution_time=execution.execution_time,
            resource_usage=execution.resource_usage or {},
            metadata=execution.metadata or {},
        )

        return response

    def _format_filters(
        self,
        task_id: Optional[str],
        status: Optional[str],
        agent_type: Optional[str]
    ) -> str:
        """格式化过滤条件用于日志"""
        filters = []
        if task_id:
            filters.append(f"任务={task_id}")
        if status:
            filters.append(f"状态={status}")
        if agent_type:
            filters.append(f"智能体类型={agent_type}")

        if filters:
            return f"，过滤条件: {', '.join(filters)}"
        else:
            return ""