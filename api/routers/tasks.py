"""任务管理API

处理任务创建、更新、分配和执行。
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, Body, BackgroundTasks
from fastapi.responses import JSONResponse
import loguru

from config.settings import settings
from services.task_service import TaskService
from models.schemas import (
    TaskCreate,
    TaskUpdate,
    TaskResponse,
    TaskExecutionRequest,
    TaskDependencyUpdate,
    TaskStatsResponse,
)

logger = loguru.logger
router = APIRouter()

# 初始化服务
task_service = TaskService()

@router.post("/", response_model=TaskResponse)
async def create_task(
    task: TaskCreate,
    background_tasks: BackgroundTasks
):
    """
    创建新任务

    可以指定任务类型（开发、评审、测试等）、优先级和分配对象。
    """
    try:
        result = await task_service.create_task(
            task_data=task,
            background_tasks=background_tasks
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"创建任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail="创建任务失败")

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """
    获取任务详情

    包括任务信息、依赖关系、执行记录和代码工件。
    """
    try:
        task = await task_service.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        return task
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取任务失败")

@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    task_update: TaskUpdate
):
    """
    更新任务信息

    可以更新任务状态、优先级、描述等信息。
    """
    try:
        result = await task_service.update_task(
            task_id=task_id,
            update_data=task_update
        )
        if not result:
            raise HTTPException(status_code=404, detail="任务不存在")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail="更新任务失败")

@router.delete("/{task_id}")
async def delete_task(task_id: str):
    """
    删除任务

    任务删除后，相关执行记录和代码工件也会被删除。
    """
    try:
        success = await task_service.delete_task(task_id)
        if not success:
            raise HTTPException(status_code=404, detail="任务不存在")
        return {"message": "任务删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail="删除任务失败")

@router.get("/", response_model=List[TaskResponse])
async def list_tasks(
    skip: int = Query(0, ge=0, description="跳过数量"),
    limit: int = Query(100, ge=1, le=1000, description="返回数量"),
    project_id: Optional[str] = Query(None, description="项目ID过滤"),
    requirement_id: Optional[str] = Query(None, description="需求ID过滤"),
    status: Optional[str] = Query(None, description="状态过滤"),
    task_type: Optional[str] = Query(None, description="任务类型过滤"),
    assigned_to: Optional[str] = Query(None, description="分配对象过滤"),
    priority: Optional[str] = Query(None, description="优先级过滤")
):
    """
    列出任务

    支持多种过滤条件：项目、需求、状态、类型、分配对象等。
    """
    try:
        tasks = await task_service.list_tasks(
            skip=skip,
            limit=limit,
            project_id=project_id,
            requirement_id=requirement_id,
            status=status,
            task_type=task_type,
            assigned_to=assigned_to,
            priority=priority
        )
        return tasks
    except Exception as e:
        logger.error(f"列出任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail="列出任务失败")

@router.post("/{task_id}/execute")
async def execute_task(
    task_id: str,
    execution_request: TaskExecutionRequest,
    background_tasks: BackgroundTasks
):
    """
    执行任务

    启动任务执行流程，包括代码生成、评审、测试等。
    """
    try:
        task = await task_service.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        # 检查任务状态
        if task.status not in ["pending", "failed"]:
            raise HTTPException(status_code=400, detail="任务当前状态不可执行")

        # 启动异步执行
        execution_id = await task_service.start_task_execution(
            task_id=task_id,
            execution_request=execution_request,
            background_tasks=background_tasks
        )

        return {
            "execution_id": execution_id,
            "message": "任务执行已启动",
            "status": "processing"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动任务执行失败: {str(e)}")
        raise HTTPException(status_code=500, detail="启动任务执行失败")

@router.get("/{task_id}/executions")
async def list_task_executions(task_id: str):
    """
    列出任务的所有执行记录
    """
    try:
        executions = await task_service.list_task_executions(task_id)
        if executions is None:
            raise HTTPException(status_code=404, detail="任务不存在")
        return executions
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"列出任务执行记录失败: {str(e)}")
        raise HTTPException(status_code=500, detail="列出任务执行记录失败")

@router.post("/{task_id}/dependencies")
async def add_task_dependency(
    task_id: str,
    dependency_update: TaskDependencyUpdate
):
    """
    添加任务依赖

    指定当前任务依赖于另一个任务。
    """
    try:
        success = await task_service.add_task_dependency(
            task_id=task_id,
            depends_on_id=dependency_update.depends_on_id
        )
        if not success:
            raise HTTPException(status_code=400, detail="添加依赖失败")
        return {"message": "依赖添加成功"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加任务依赖失败: {str(e)}")
        raise HTTPException(status_code=500, detail="添加任务依赖失败")

@router.delete("/{task_id}/dependencies/{depends_on_id}")
async def remove_task_dependency(
    task_id: str,
    depends_on_id: str
):
    """
    移除任务依赖
    """
    try:
        success = await task_service.remove_task_dependency(
            task_id=task_id,
            depends_on_id=depends_on_id
        )
        if not success:
            raise HTTPException(status_code=400, detail="移除依赖失败")
        return {"message": "依赖移除成功"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"移除任务依赖失败: {str(e)}")
        raise HTTPException(status_code=500, detail="移除任务依赖失败")

@router.post("/{task_id}/assign")
async def assign_task(
    task_id: str,
    user_id: str = Body(..., embed=True, description="分配的用户ID")
):
    """
    分配任务给用户
    """
    try:
        success = await task_service.assign_task(
            task_id=task_id,
            user_id=user_id
        )
        if not success:
            raise HTTPException(status_code=400, detail="分配任务失败")
        return {"message": "任务分配成功"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"分配任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail="分配任务失败")

@router.post("/{task_id}/start")
async def start_task(task_id: str):
    """
    开始任务执行
    """
    try:
        success = await task_service.start_task(task_id)
        if not success:
            raise HTTPException(status_code=400, detail="开始任务失败")
        return {"message": "任务开始执行"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"开始任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail="开始任务失败")

@router.post("/{task_id}/complete")
async def complete_task(task_id: str):
    """
    标记任务为完成
    """
    try:
        success = await task_service.complete_task(task_id)
        if not success:
            raise HTTPException(status_code=400, detail="完成任务失败")
        return {"message": "任务完成"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"完成任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail="完成任务失败")

@router.post("/{task_id}/fail")
async def fail_task(
    task_id: str,
    error_message: str = Body(..., embed=True, description="失败原因")
):
    """
    标记任务为失败
    """
    try:
        success = await task_service.fail_task(
            task_id=task_id,
            error_message=error_message
        )
        if not success:
            raise HTTPException(status_code=400, detail="标记任务失败失败")
        return {"message": "任务标记为失败"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"标记任务失败失败: {str(e)}")
        raise HTTPException(status_code=500, detail="标记任务失败失败")

@router.get("/{task_id}/stats", response_model=TaskStatsResponse)
async def get_task_stats(task_id: str):
    """
    获取任务统计信息

    包括执行次数、成功/失败次数、平均执行时间等。
    """
    try:
        stats = await task_service.get_task_stats(task_id)
        if not stats:
            raise HTTPException(status_code=404, detail="任务不存在")
        return stats
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取任务统计失败")

@router.get("/project/{project_id}/stats", response_model=TaskStatsResponse)
async def get_project_tasks_stats(project_id: str):
    """
    获取项目的任务统计信息
    """
    try:
        stats = await task_service.get_project_tasks_stats(project_id)
        if not stats:
            raise HTTPException(status_code=404, detail="项目不存在")
        return stats
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取项目任务统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取项目任务统计失败")