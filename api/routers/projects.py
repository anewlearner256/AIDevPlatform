"""项目管理API

处理项目创建、更新、成员管理和项目相关操作。
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, Body
from fastapi.responses import JSONResponse
import loguru

from config.settings import settings
from services.project_service import ProjectService
from models.schemas import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectMemberUpdate,
    ProjectStatsResponse,
)

logger = loguru.logger
router = APIRouter()

# 初始化服务
project_service = ProjectService()

@router.post("/", response_model=ProjectResponse)
async def create_project(
    project: ProjectCreate,
    user_id: str = Body(..., description="创建者用户ID")
):
    """
    创建新项目

    需要提供项目名称、描述和可见性设置。
    """
    try:
        result = await project_service.create_project(
            project_data=project,
            user_id=user_id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"创建项目失败: {str(e)}")
        raise HTTPException(status_code=500, detail="创建项目失败")

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str):
    """
    获取项目详情

    包括项目基本信息、成员列表和统计信息。
    """
    try:
        project = await project_service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        return project
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取项目失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取项目失败")

@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    project_update: ProjectUpdate
):
    """
    更新项目信息

    可以更新项目名称、描述、状态和可见性。
    """
    try:
        result = await project_service.update_project(
            project_id=project_id,
            update_data=project_update
        )
        if not result:
            raise HTTPException(status_code=404, detail="项目不存在")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新项目失败: {str(e)}")
        raise HTTPException(status_code=500, detail="更新项目失败")

@router.delete("/{project_id}")
async def delete_project(project_id: str):
    """
    删除项目

    项目删除后，相关需求、任务等也会被删除。
    """
    try:
        success = await project_service.delete_project(project_id)
        if not success:
            raise HTTPException(status_code=404, detail="项目不存在")
        return {"message": "项目删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除项目失败: {str(e)}")
        raise HTTPException(status_code=500, detail="删除项目失败")

@router.get("/", response_model=List[ProjectResponse])
async def list_projects(
    skip: int = Query(0, ge=0, description="跳过数量"),
    limit: int = Query(100, ge=1, le=1000, description="返回数量"),
    status: Optional[str] = Query(None, description="状态过滤"),
    visibility: Optional[str] = Query(None, description="可见性过滤"),
    user_id: Optional[str] = Query(None, description="用户ID过滤（用户参与的项目）")
):
    """
    列出项目

    支持分页、状态过滤和可见性过滤。
    """
    try:
        projects = await project_service.list_projects(
            skip=skip,
            limit=limit,
            status=status,
            visibility=visibility,
            user_id=user_id
        )
        return projects
    except Exception as e:
        logger.error(f"列出项目失败: {str(e)}")
        raise HTTPException(status_code=500, detail="列出项目失败")

@router.get("/{project_id}/stats", response_model=ProjectStatsResponse)
async def get_project_stats(project_id: str):
    """
    获取项目统计信息

    包括需求数量、任务数量、完成率等。
    """
    try:
        stats = await project_service.get_project_stats(project_id)
        if not stats:
            raise HTTPException(status_code=404, detail="项目不存在")
        return stats
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取项目统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取项目统计失败")

@router.post("/{project_id}/members")
async def add_project_member(
    project_id: str,
    member_update: ProjectMemberUpdate
):
    """
    添加项目成员

    将用户添加到项目中，并指定角色。
    """
    try:
        success = await project_service.add_project_member(
            project_id=project_id,
            user_id=member_update.user_id,
            role=member_update.role
        )
        if not success:
            raise HTTPException(status_code=400, detail="添加成员失败")
        return {"message": "成员添加成功"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加项目成员失败: {str(e)}")
        raise HTTPException(status_code=500, detail="添加项目成员失败")

@router.delete("/{project_id}/members/{user_id}")
async def remove_project_member(
    project_id: str,
    user_id: str
):
    """
    移除项目成员
    """
    try:
        success = await project_service.remove_project_member(
            project_id=project_id,
            user_id=user_id
        )
        if not success:
            raise HTTPException(status_code=400, detail="移除成员失败")
        return {"message": "成员移除成功"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"移除项目成员失败: {str(e)}")
        raise HTTPException(status_code=500, detail="移除项目成员失败")

@router.get("/{project_id}/members")
async def list_project_members(project_id: str):
    """
    列出项目所有成员
    """
    try:
        members = await project_service.list_project_members(project_id)
        if members is None:
            raise HTTPException(status_code=404, detail="项目不存在")
        return members
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"列出项目成员失败: {str(e)}")
        raise HTTPException(status_code=500, detail="列出项目成员失败")

@router.post("/{project_id}/archive")
async def archive_project(project_id: str):
    """
    归档项目

    归档后项目不再活跃，但数据保留。
    """
    try:
        success = await project_service.archive_project(project_id)
        if not success:
            raise HTTPException(status_code=404, detail="项目不存在")
        return {"message": "项目归档成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"归档项目失败: {str(e)}")
        raise HTTPException(status_code=500, detail="归档项目失败")

@router.post("/{project_id}/activate")
async def activate_project(project_id: str):
    """
    激活已归档的项目
    """
    try:
        success = await project_service.activate_project(project_id)
        if not success:
            raise HTTPException(status_code=404, detail="项目不存在")
        return {"message": "项目激活成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"激活项目失败: {str(e)}")
        raise HTTPException(status_code=500, detail="激活项目失败")