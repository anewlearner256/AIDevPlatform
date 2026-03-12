"""项目服务

管理项目和相关业务逻辑。
"""

from typing import List, Dict, Any, Optional
import loguru

from models.schemas import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
)
from models.database import get_async_session
from models.database import Project as ProjectModel
from models.database import User as UserModel
from models.database import project_members

logger = loguru.logger

class ProjectService:
    """项目服务"""

    async def create_project(
        self,
        project_data: ProjectCreate,
        user_id: str
    ) -> ProjectResponse:
        """
        创建项目

        Args:
            project_data: 项目数据
            user_id: 创建者用户ID

        Returns:
            项目响应
        """
        try:
            async with get_async_session() as session:
                # 创建项目
                project = ProjectModel(
                    name=project_data.name,
                    description=project_data.description,
                    visibility=project_data.visibility,
                    created_by=user_id,
                    metadata=project_data.metadata or {},
                )

                session.add(project)
                await session.commit()
                await session.refresh(project)

                # 添加创建者为项目成员
                await self._add_project_member(session, project.id, user_id, "owner")

                # 转换为响应
                response = ProjectResponse(
                    id=project.id,
                    name=project.name,
                    description=project.description,
                    status=project.status,
                    visibility=project.visibility,
                    created_by=project.created_by,
                    created_at=project.created_at,
                    updated_at=project.updated_at,
                    metadata=project.metadata or {},
                )

                logger.info(f"项目创建成功: {project.id}，名称: {project.name}")
                return response

        except Exception as e:
            logger.error(f"创建项目失败: {str(e)}")
            raise

    async def get_project(self, project_id: str) -> Optional[ProjectResponse]:
        """
        获取项目

        Args:
            project_id: 项目ID

        Returns:
            项目响应
        """
        try:
            async with get_async_session() as session:
                project = await session.get(ProjectModel, project_id)
                if not project:
                    return None

                # 转换为响应
                response = ProjectResponse(
                    id=project.id,
                    name=project.name,
                    description=project.description,
                    status=project.status,
                    visibility=project.visibility,
                    created_by=project.created_by,
                    created_at=project.created_at,
                    updated_at=project.updated_at,
                    metadata=project.metadata or {},
                )

                return response

        except Exception as e:
            logger.error(f"获取项目失败: {project_id}，错误: {str(e)}")
            raise

    async def update_project(
        self,
        project_id: str,
        update_data: ProjectUpdate
    ) -> bool:
        """
        更新项目

        Args:
            project_id: 项目ID
            update_data: 更新数据

        Returns:
            是否成功
        """
        try:
            async with get_async_session() as session:
                project = await session.get(ProjectModel, project_id)
                if not project:
                    return False

                # 更新字段
                if update_data.name is not None:
                    project.name = update_data.name

                if update_data.description is not None:
                    project.description = update_data.description

                if update_data.status is not None:
                    project.status = update_data.status

                if update_data.visibility is not None:
                    project.visibility = update_data.visibility

                if update_data.metadata is not None:
                    # 合并元数据
                    current_metadata = project.metadata or {}
                    current_metadata.update(update_data.metadata)
                    project.metadata = current_metadata

                await session.commit()

                logger.info(f"项目更新成功: {project_id}")
                return True

        except Exception as e:
            logger.error(f"更新项目失败: {project_id}，错误: {str(e)}")
            return False

    async def delete_project(self, project_id: str) -> bool:
        """
        删除项目

        Args:
            project_id: 项目ID

        Returns:
            是否成功
        """
        try:
            async with get_async_session() as session:
                project = await session.get(ProjectModel, project_id)
                if not project:
                    return False

                # 删除项目（级联删除由数据库处理）
                await session.delete(project)
                await session.commit()

                logger.info(f"项目删除成功: {project_id}")
                return True

        except Exception as e:
            logger.error(f"删除项目失败: {project_id}，错误: {str(e)}")
            return False

    async def list_projects(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 100,
        include_public: bool = True
    ) -> List[ProjectResponse]:
        """
        列出用户可访问的项目

        Args:
            user_id: 用户ID
            skip: 跳过数量
            limit: 返回数量
            include_public: 是否包含公开项目

        Returns:
            项目列表
        """
        try:
            async with get_async_session() as session:
                from sqlalchemy import select, or_

                # 构建查询：用户创建的项目 + 用户参与的项目 + 公开项目
                query = select(ProjectModel)

                conditions = []

                # 用户创建的项目
                conditions.append(ProjectModel.created_by == user_id)

                # 用户参与的项目
                from sqlalchemy import exists
                member_subquery = select(1).where(
                    (project_members.c.project_id == ProjectModel.id) &
                    (project_members.c.user_id == user_id)
                ).exists()
                conditions.append(member_subquery)

                # 公开项目
                if include_public:
                    conditions.append(ProjectModel.visibility == "public")

                # 应用条件
                if conditions:
                    query = query.where(or_(*conditions))

                # 计数
                from sqlalchemy.sql import func
                count_query = select(func.count()).select_from(ProjectModel)
                if conditions:
                    count_query = count_query.where(or_(*conditions))

                total = await session.scalar(count_query)

                # 分页和排序
                query = query.offset(skip).limit(limit)
                query = query.order_by(ProjectModel.updated_at.desc())

                # 执行查询
                result = await session.execute(query)
                projects = result.scalars().all()

                # 转换为响应
                responses = []
                for project in projects:
                    response = ProjectResponse(
                        id=project.id,
                        name=project.name,
                        description=project.description,
                        status=project.status,
                        visibility=project.visibility,
                        created_by=project.created_by,
                        created_at=project.created_at,
                        updated_at=project.updated_at,
                        metadata=project.metadata or {},
                    )
                    responses.append(response)

                logger.info(f"列出项目成功，用户: {user_id}，总数: {total}")
                return responses

        except Exception as e:
            logger.error(f"列出项目失败: {str(e)}")
            raise

    async def add_project_member(
        self,
        project_id: str,
        user_id: str,
        role: str = "member"
    ) -> bool:
        """
        添加项目成员

        Args:
            project_id: 项目ID
            user_id: 用户ID
            role: 角色

        Returns:
            是否成功
        """
        try:
            async with get_async_session() as session:
                # 检查项目是否存在
                project = await session.get(ProjectModel, project_id)
                if not project:
                    return False

                # 检查用户是否存在
                user = await session.get(UserModel, user_id)
                if not user:
                    return False

                # 检查是否已是成员
                from sqlalchemy import select
                query = select(project_members).where(
                    (project_members.c.project_id == project_id) &
                    (project_members.c.user_id == user_id)
                )
                result = await session.execute(query)
                existing = result.first()

                if existing:
                    # 更新角色
                    update_stmt = project_members.update().where(
                        (project_members.c.project_id == project_id) &
                        (project_members.c.user_id == user_id)
                    ).values(role=role)
                    await session.execute(update_stmt)
                else:
                    # 添加新成员
                    insert_stmt = project_members.insert().values(
                        project_id=project_id,
                        user_id=user_id,
                        role=role
                    )
                    await session.execute(insert_stmt)

                await session.commit()

                logger.info(f"添加项目成员成功: 项目={project_id}，用户={user_id}，角色={role}")
                return True

        except Exception as e:
            logger.error(f"添加项目成员失败: {str(e)}")
            return False

    async def remove_project_member(
        self,
        project_id: str,
        user_id: str
    ) -> bool:
        """
        移除项目成员

        Args:
            project_id: 项目ID
            user_id: 用户ID

        Returns:
            是否成功
        """
        try:
            async with get_async_session() as session:
                # 不能移除项目创建者
                project = await session.get(ProjectModel, project_id)
                if not project:
                    return False

                if project.created_by == user_id:
                    logger.warning(f"不能移除项目创建者: {project_id}，用户: {user_id}")
                    return False

                # 移除成员
                delete_stmt = project_members.delete().where(
                    (project_members.c.project_id == project_id) &
                    (project_members.c.user_id == user_id)
                )
                result = await session.execute(delete_stmt)
                await session.commit()

                if result.rowcount > 0:
                    logger.info(f"移除项目成员成功: 项目={project_id}，用户={user_id}")
                    return True
                else:
                    return False

        except Exception as e:
            logger.error(f"移除项目成员失败: {str(e)}")
            return False

    async def get_project_members(
        self,
        project_id: str
    ) -> List[Dict[str, Any]]:
        """
        获取项目成员

        Args:
            project_id: 项目ID

        Returns:
            成员列表
        """
        try:
            async with get_async_session() as session:
                from sqlalchemy import select

                # 查询项目成员
                query = select(
                    UserModel,
                    project_members.c.role,
                    project_members.c.joined_at
                ).join(
                    project_members,
                    UserModel.id == project_members.c.user_id
                ).where(
                    project_members.c.project_id == project_id
                )

                result = await session.execute(query)
                rows = result.all()

                # 构建响应
                members = []
                for user, role, joined_at in rows:
                    members.append({
                        "user_id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "full_name": user.full_name,
                        "role": role,
                        "joined_at": joined_at,
                        "is_owner": user.id == (await session.get(ProjectModel, project_id)).created_by
                    })

                logger.info(f"获取项目成员成功: {project_id}，成员数: {len(members)}")
                return members

        except Exception as e:
            logger.error(f"获取项目成员失败: {project_id}，错误: {str(e)}")
            raise

    async def is_user_project_member(
        self,
        project_id: str,
        user_id: str
    ) -> bool:
        """
        检查用户是否是项目成员

        Args:
            project_id: 项目ID
            user_id: 用户ID

        Returns:
            是否是成员
        """
        try:
            async with get_async_session() as session:
                from sqlalchemy import select, exists

                # 检查项目是否存在
                project = await session.get(ProjectModel, project_id)
                if not project:
                    return False

                # 项目创建者自动是成员
                if project.created_by == user_id:
                    return True

                # 检查成员表
                query = select(exists().where(
                    (project_members.c.project_id == project_id) &
                    (project_members.c.user_id == user_id)
                ))

                result = await session.scalar(query)
                return bool(result)

        except Exception as e:
            logger.error(f"检查项目成员失败: {str(e)}")
            return False

    async def is_user_project_owner(
        self,
        project_id: str,
        user_id: str
    ) -> bool:
        """
        检查用户是否是项目所有者

        Args:
            project_id: 项目ID
            user_id: 用户ID

        Returns:
            是否是所有者
        """
        try:
            async with get_async_session() as session:
                project = await session.get(ProjectModel, project_id)
                if not project:
                    return False

                return project.created_by == user_id

        except Exception as e:
            logger.error(f"检查项目所有者失败: {str(e)}")
            return False

    async def get_project_statistics(
        self,
        project_id: str
    ) -> Dict[str, Any]:
        """
        获取项目统计信息

        Args:
            project_id: 项目ID

        Returns:
            统计信息
        """
        try:
            async with get_async_session() as session:
                from sqlalchemy import select, func
                from models.database import (
                    Requirement as RequirementModel,
                    Task as TaskModel,
                    TaskExecution as TaskExecutionModel
                )

                # 检查项目是否存在
                project = await session.get(ProjectModel, project_id)
                if not project:
                    raise ValueError(f"项目不存在: {project_id}")

                # 需求统计
                req_query = select(func.count()).where(
                    RequirementModel.project_id == project_id
                )
                total_requirements = await session.scalar(req_query)

                req_status_query = select(
                    RequirementModel.status,
                    func.count(RequirementModel.id)
                ).where(
                    RequirementModel.project_id == project_id
                ).group_by(RequirementModel.status)
                req_status_result = await session.execute(req_status_query)
                requirement_status = {row[0]: row[1] for row in req_status_result}

                # 任务统计
                task_query = select(func.count()).where(
                    TaskModel.project_id == project_id
                )
                total_tasks = await session.scalar(task_query)

                task_status_query = select(
                    TaskModel.status,
                    func.count(TaskModel.id)
                ).where(
                    TaskModel.project_id == project_id
                ).group_by(TaskModel.status)
                task_status_result = await session.execute(task_status_query)
                task_status = {row[0]: row[1] for row in task_status_result}

                task_type_query = select(
                    TaskModel.task_type,
                    func.count(TaskModel.id)
                ).where(
                    TaskModel.project_id == project_id
                ).group_by(TaskModel.task_type)
                task_type_result = await session.execute(task_type_query)
                task_types = {row[0]: row[1] for row in task_type_result}

                # 执行统计
                exec_query = select(func.count()).select_from(TaskExecutionModel).join(
                    TaskModel, TaskExecutionModel.task_id == TaskModel.id
                ).where(
                    TaskModel.project_id == project_id
                )
                total_executions = await session.scalar(exec_query)

                exec_status_query = select(
                    TaskExecutionModel.status,
                    func.count(TaskExecutionModel.id)
                ).select_from(TaskExecutionModel).join(
                    TaskModel, TaskExecutionModel.task_id == TaskModel.id
                ).where(
                    TaskModel.project_id == project_id
                ).group_by(TaskExecutionModel.status)
                exec_status_result = await session.execute(exec_status_query)
                execution_status = {row[0]: row[1] for row in exec_status_result}

                statistics = {
                    "project_id": project_id,
                    "project_name": project.name,
                    "total_requirements": total_requirements,
                    "requirement_status": requirement_status,
                    "total_tasks": total_tasks,
                    "task_status": task_status,
                    "task_types": task_types,
                    "total_executions": total_executions,
                    "execution_status": execution_status,
                    "member_count": len(await self.get_project_members(project_id)),
                }

                logger.info(f"获取项目统计成功: {project_id}")
                return statistics

        except Exception as e:
            logger.error(f"获取项目统计失败: {project_id}，错误: {str(e)}")
            raise

    async def _add_project_member(
        self,
        session,
        project_id: str,
        user_id: str,
        role: str
    ):
        """添加项目成员（内部方法）"""
        insert_stmt = project_members.insert().values(
            project_id=project_id,
            user_id=user_id,
            role=role
        )
        await session.execute(insert_stmt)