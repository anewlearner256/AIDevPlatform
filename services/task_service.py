"""任务服务

管理任务和相关业务逻辑。
"""

from typing import List, Dict, Any, Optional
import loguru

from models.schemas import (
    TaskCreate,
    TaskUpdate,
    TaskResponse,
)
from models.database import get_async_session
from models.database import (
    Task as TaskModel,
    Project as ProjectModel,
    Requirement as RequirementModel,
    User as UserModel,
    task_dependencies
)

logger = loguru.logger

class TaskService:
    """任务服务"""

    async def create_task(
        self,
        task_data: TaskCreate
    ) -> TaskResponse:
        """
        创建任务

        Args:
            task_data: 任务数据

        Returns:
            任务响应
        """
        try:
            async with get_async_session() as session:
                # 验证项目存在
                project = await session.get(ProjectModel, task_data.project_id)
                if not project:
                    raise ValueError(f"项目不存在: {task_data.project_id}")

                # 验证需求存在（如果提供）
                if task_data.requirement_id:
                    requirement = await session.get(RequirementModel, task_data.requirement_id)
                    if not requirement:
                        raise ValueError(f"需求不存在: {task_data.requirement_id}")

                # 验证分配的用户存在（如果提供）
                if task_data.assigned_to:
                    user = await session.get(UserModel, task_data.assigned_to)
                    if not user:
                        raise ValueError(f"用户不存在: {task_data.assigned_to}")

                # 创建任务
                task = TaskModel(
                    project_id=task_data.project_id,
                    requirement_id=task_data.requirement_id,
                    title=task_data.title,
                    description=task_data.description,
                    task_type=task_data.task_type,
                    priority=task_data.priority,
                    estimated_hours=task_data.estimated_hours,
                    assigned_to=task_data.assigned_to,
                    due_date=task_data.due_date,
                    metadata=task_data.metadata or {},
                )

                session.add(task)
                await session.commit()
                await session.refresh(task)

                # 添加依赖关系
                if task_data.dependencies:
                    await self._add_task_dependencies(
                        session, task.id, task_data.dependencies
                    )

                # 转换为响应
                response = await self._task_to_response(session, task)

                logger.info(f"任务创建成功: {task.id}，标题: {task.title}")
                return response

        except Exception as e:
            logger.error(f"创建任务失败: {str(e)}")
            raise

    async def get_task(self, task_id: str) -> Optional[TaskResponse]:
        """
        获取任务

        Args:
            task_id: 任务ID

        Returns:
            任务响应
        """
        try:
            async with get_async_session() as session:
                task = await session.get(TaskModel, task_id)
                if not task:
                    return None

                # 转换为响应
                response = await self._task_to_response(session, task)
                return response

        except Exception as e:
            logger.error(f"获取任务失败: {task_id}，错误: {str(e)}")
            raise

    async def update_task(
        self,
        task_id: str,
        update_data: TaskUpdate
    ) -> bool:
        """
        更新任务

        Args:
            task_id: 任务ID
            update_data: 更新数据

        Returns:
            是否成功
        """
        try:
            async with get_async_session() as session:
                task = await session.get(TaskModel, task_id)
                if not task:
                    return False

                # 验证分配的用户存在（如果提供）
                if update_data.assigned_to is not None:
                    if update_data.assigned_to:
                        user = await session.get(UserModel, update_data.assigned_to)
                        if not user:
                            raise ValueError(f"用户不存在: {update_data.assigned_to}")
                    task.assigned_to = update_data.assigned_to

                # 更新字段
                if update_data.title is not None:
                    task.title = update_data.title

                if update_data.description is not None:
                    task.description = update_data.description

                if update_data.status is not None:
                    # 状态转换逻辑
                    old_status = task.status
                    new_status = update_data.status

                    if new_status == "in_progress" and old_status == "pending":
                        task.started_at = update_data.started_at or task.started_at

                    if new_status == "completed" and old_status != "completed":
                        task.completed_at = update_data.completed_at or task.completed_at

                    task.status = new_status

                if update_data.priority is not None:
                    task.priority = update_data.priority

                if update_data.estimated_hours is not None:
                    task.estimated_hours = update_data.estimated_hours

                if update_data.actual_hours is not None:
                    task.actual_hours = update_data.actual_hours

                if update_data.due_date is not None:
                    task.due_date = update_data.due_date

                if update_data.started_at is not None:
                    task.started_at = update_data.started_at

                if update_data.completed_at is not None:
                    task.completed_at = update_data.completed_at

                if update_data.metadata is not None:
                    # 合并元数据
                    current_metadata = task.metadata or {}
                    current_metadata.update(update_data.metadata)
                    task.metadata = current_metadata

                await session.commit()

                logger.info(f"任务更新成功: {task_id}")
                return True

        except Exception as e:
            logger.error(f"更新任务失败: {task_id}，错误: {str(e)}")
            return False

    async def delete_task(self, task_id: str) -> bool:
        """
        删除任务

        Args:
            task_id: 任务ID

        Returns:
            是否成功
        """
        try:
            async with get_async_session() as session:
                task = await session.get(TaskModel, task_id)
                if not task:
                    return False

                # 删除任务（级联删除由数据库处理）
                await session.delete(task)
                await session.commit()

                logger.info(f"任务删除成功: {task_id}")
                return True

        except Exception as e:
            logger.error(f"删除任务失败: {task_id}，错误: {str(e)}")
            return False

    async def list_tasks(
        self,
        project_id: Optional[str] = None,
        requirement_id: Optional[str] = None,
        assigned_to: Optional[str] = None,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[TaskResponse]:
        """
        列出任务

        Args:
            project_id: 项目ID过滤
            requirement_id: 需求ID过滤
            assigned_to: 分配用户过滤
            status: 状态过滤
            task_type: 任务类型过滤
            skip: 跳过数量
            limit: 返回数量

        Returns:
            任务列表
        """
        try:
            async with get_async_session() as session:
                from sqlalchemy import select

                # 构建查询
                query = select(TaskModel)

                # 应用过滤条件
                if project_id:
                    query = query.where(TaskModel.project_id == project_id)

                if requirement_id:
                    query = query.where(TaskModel.requirement_id == requirement_id)

                if assigned_to:
                    query = query.where(TaskModel.assigned_to == assigned_to)

                if status:
                    query = query.where(TaskModel.status == status)

                if task_type:
                    query = query.where(TaskModel.task_type == task_type)

                # 计数
                from sqlalchemy.sql import func
                count_query = select(func.count()).select_from(TaskModel)

                if project_id:
                    count_query = count_query.where(TaskModel.project_id == project_id)

                if requirement_id:
                    count_query = count_query.where(TaskModel.requirement_id == requirement_id)

                if assigned_to:
                    count_query = count_query.where(TaskModel.assigned_to == assigned_to)

                if status:
                    count_query = count_query.where(TaskModel.status == status)

                if task_type:
                    count_query = count_query.where(TaskModel.task_type == task_type)

                total = await session.scalar(count_query)

                # 分页和排序
                query = query.offset(skip).limit(limit)
                query = query.order_by(
                    TaskModel.priority.desc(),
                    TaskModel.created_at.desc()
                )

                # 执行查询
                result = await session.execute(query)
                tasks = result.scalars().all()

                # 转换为响应
                responses = []
                for task in tasks:
                    response = await self._task_to_response(session, task)
                    responses.append(response)

                filter_str = self._format_filters(
                    project_id, requirement_id, assigned_to, status, task_type
                )
                logger.info(f"列出任务成功{filter_str}，总数: {total}")
                return responses

        except Exception as e:
            logger.error(f"列出任务失败: {str(e)}")
            raise

    async def add_task_dependency(
        self,
        task_id: str,
        depends_on_id: str
    ) -> bool:
        """
        添加任务依赖

        Args:
            task_id: 任务ID
            depends_on_id: 依赖的任务ID

        Returns:
            是否成功
        """
        try:
            async with get_async_session() as session:
                # 检查任务存在
                task = await session.get(TaskModel, task_id)
                if not task:
                    return False

                depends_on_task = await session.get(TaskModel, depends_on_id)
                if not depends_on_task:
                    return False

                # 检查循环依赖
                if await self._has_dependency_cycle(session, task_id, depends_on_id):
                    logger.warning(f"检测到循环依赖: {task_id} -> {depends_on_id}")
                    return False

                # 添加依赖
                insert_stmt = task_dependencies.insert().values(
                    task_id=task_id,
                    depends_on_id=depends_on_id
                )

                try:
                    await session.execute(insert_stmt)
                    await session.commit()

                    logger.info(f"添加任务依赖成功: {task_id} -> {depends_on_id}")
                    return True

                except Exception:
                    # 依赖可能已存在
                    await session.rollback()
                    return False

        except Exception as e:
            logger.error(f"添加任务依赖失败: {str(e)}")
            return False

    async def remove_task_dependency(
        self,
        task_id: str,
        depends_on_id: str
    ) -> bool:
        """
        移除任务依赖

        Args:
            task_id: 任务ID
            depends_on_id: 依赖的任务ID

        Returns:
            是否成功
        """
        try:
            async with get_async_session() as session:
                delete_stmt = task_dependencies.delete().where(
                    (task_dependencies.c.task_id == task_id) &
                    (task_dependencies.c.depends_on_id == depends_on_id)
                )

                result = await session.execute(delete_stmt)
                await session.commit()

                if result.rowcount > 0:
                    logger.info(f"移除任务依赖成功: {task_id} -> {depends_on_id}")
                    return True
                else:
                    return False

        except Exception as e:
            logger.error(f"移除任务依赖失败: {str(e)}")
            return False

    async def get_task_dependencies(self, task_id: str) -> List[str]:
        """
        获取任务依赖

        Args:
            task_id: 任务ID

        Returns:
            依赖的任务ID列表
        """
        try:
            async with get_async_session() as session:
                from sqlalchemy import select

                query = select(task_dependencies.c.depends_on_id).where(
                    task_dependencies.c.task_id == task_id
                )

                result = await session.execute(query)
                dependencies = [row[0] for row in result]

                return dependencies

        except Exception as e:
            logger.error(f"获取任务依赖失败: {task_id}，错误: {str(e)}")
            raise

    async def get_dependent_tasks(self, task_id: str) -> List[str]:
        """
        获取依赖此任务的任务

        Args:
            task_id: 任务ID

        Returns:
            依赖此任务的任务ID列表
        """
        try:
            async with get_async_session() as session:
                from sqlalchemy import select

                query = select(task_dependencies.c.task_id).where(
                    task_dependencies.c.depends_on_id == task_id
                )

                result = await session.execute(query)
                dependents = [row[0] for row in result]

                return dependents

        except Exception as e:
            logger.error(f"获取依赖任务失败: {task_id}，错误: {str(e)}")
            raise

    async def get_task_statistics(
        self,
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取任务统计信息

        Args:
            project_id: 项目ID（可选）

        Returns:
            统计信息
        """
        try:
            async with get_async_session() as session:
                from sqlalchemy import select, func

                # 构建查询
                query = select(TaskModel)

                if project_id:
                    query = query.where(TaskModel.project_id == project_id)

                # 执行查询获取所有任务
                result = await session.execute(query)
                tasks = result.scalars().all()

                if not tasks:
                    return {
                        "total_tasks": 0,
                        "status_distribution": {},
                        "type_distribution": {},
                        "priority_distribution": {},
                        "avg_estimated_hours": 0,
                        "total_estimated_hours": 0,
                        "total_actual_hours": 0,
                        "completion_rate": 0,
                    }

                # 计算统计
                total_tasks = len(tasks)
                completed_tasks = sum(1 for t in tasks if t.status == "completed")
                completion_rate = completed_tasks / total_tasks if total_tasks > 0 else 0

                status_distribution = {}
                type_distribution = {}
                priority_distribution = {}

                total_estimated_hours = 0
                total_actual_hours = 0

                for task in tasks:
                    # 状态分布
                    status_distribution[task.status] = status_distribution.get(task.status, 0) + 1

                    # 类型分布
                    type_distribution[task.task_type] = type_distribution.get(task.task_type, 0) + 1

                    # 优先级分布
                    priority_distribution[task.priority] = priority_distribution.get(task.priority, 0) + 1

                    # 工时统计
                    total_estimated_hours += task.estimated_hours or 0
                    total_actual_hours += task.actual_hours or 0

                avg_estimated_hours = total_estimated_hours / total_tasks if total_tasks > 0 else 0

                statistics = {
                    "total_tasks": total_tasks,
                    "status_distribution": status_distribution,
                    "type_distribution": type_distribution,
                    "priority_distribution": priority_distribution,
                    "avg_estimated_hours": avg_estimated_hours,
                    "total_estimated_hours": total_estimated_hours,
                    "total_actual_hours": total_actual_hours,
                    "completion_rate": completion_rate,
                }

                if project_id:
                    statistics["project_id"] = project_id

                logger.info(f"获取任务统计成功，项目: {project_id or '所有'}，总数: {total_tasks}")
                return statistics

        except Exception as e:
            logger.error(f"获取任务统计失败: {str(e)}")
            raise

    async def _task_to_response(
        self,
        session,
        task: TaskModel
    ) -> TaskResponse:
        """将任务模型转换为响应"""
        # 获取依赖关系
        dependencies = await self.get_task_dependencies(task.id)

        response = TaskResponse(
            id=task.id,
            project_id=task.project_id,
            requirement_id=task.requirement_id,
            title=task.title,
            description=task.description,
            task_type=task.task_type,
            status=task.status,
            priority=task.priority,
            estimated_hours=task.estimated_hours,
            actual_hours=task.actual_hours,
            assigned_to=task.assigned_to,
            due_date=task.due_date,
            started_at=task.started_at,
            completed_at=task.completed_at,
            created_at=task.created_at,
            updated_at=task.updated_at,
            metadata=task.metadata or {},
            dependencies=dependencies,
        )

        return response

    async def _add_task_dependencies(
        self,
        session,
        task_id: str,
        dependency_ids: List[str]
    ):
        """添加任务依赖（内部方法）"""
        for dep_id in dependency_ids:
            # 检查依赖的任务存在
            depends_on_task = await session.get(TaskModel, dep_id)
            if depends_on_task:
                # 检查循环依赖
                if not await self._has_dependency_cycle(session, task_id, dep_id):
                    insert_stmt = task_dependencies.insert().values(
                        task_id=task_id,
                        depends_on_id=dep_id
                    )
                    try:
                        await session.execute(insert_stmt)
                    except Exception:
                        # 依赖可能已存在
                        pass

    async def _has_dependency_cycle(
        self,
        session,
        task_id: str,
        depends_on_id: str
    ) -> bool:
        """检查是否形成循环依赖"""
        # 简单的循环检查：如果depends_on_id已经依赖task_id，则形成循环
        from sqlalchemy import select

        # 检查直接依赖
        query = select(task_dependencies.c.depends_on_id).where(
            task_dependencies.c.task_id == depends_on_id
        )
        result = await session.execute(query)
        direct_deps = [row[0] for row in result]

        if task_id in direct_deps:
            return True

        # 检查间接依赖（递归）
        for dep in direct_deps:
            if await self._has_dependency_cycle(session, task_id, dep):
                return True

        return False

    def _format_filters(
        self,
        project_id: Optional[str],
        requirement_id: Optional[str],
        assigned_to: Optional[str],
        status: Optional[str],
        task_type: Optional[str]
    ) -> str:
        """格式化过滤条件用于日志"""
        filters = []
        if project_id:
            filters.append(f"项目={project_id}")
        if requirement_id:
            filters.append(f"需求={requirement_id}")
        if assigned_to:
            filters.append(f"分配用户={assigned_to}")
        if status:
            filters.append(f"状态={status}")
        if task_type:
            filters.append(f"类型={task_type}")

        if filters:
            return f"，过滤条件: {', '.join(filters)}"
        else:
            return ""