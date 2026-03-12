"""执行管理API

处理任务执行记录、结果查询和执行控制。
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, Body
from fastapi.responses import JSONResponse
import loguru

from config.settings import settings
from services.execution_service import ExecutionService
from models.schemas import (
    TaskExecutionCreate,
    TaskExecutionUpdate,
    TaskExecutionResponse,
    ExecutionResultResponse,
    ExecutionStatsResponse,
)

logger = loguru.logger
router = APIRouter()

# 初始化服务
execution_service = ExecutionService()

@router.post("/", response_model=TaskExecutionResponse)
async def create_execution(
    execution: TaskExecutionCreate
):
    """
    创建执行记录

    记录任务执行的开始时间和相关配置。
    """
    try:
        result = await execution_service.create_execution(
            execution_data=execution
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"创建执行记录失败: {str(e)}")
        raise HTTPException(status_code=500, detail="创建执行记录失败")

@router.get("/{execution_id}", response_model=TaskExecutionResponse)
async def get_execution(execution_id: str):
    """
    获取执行记录详情

    包括执行状态、输入输出数据、错误信息和资源使用情况。
    """
    try:
        execution = await execution_service.get_execution(execution_id)
        if not execution:
            raise HTTPException(status_code=404, detail="执行记录不存在")
        return execution
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取执行记录失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取执行记录失败")

@router.put("/{execution_id}", response_model=TaskExecutionResponse)
async def update_execution(
    execution_id: str,
    execution_update: TaskExecutionUpdate
):
    """
    更新执行记录

    可以更新执行状态、输出数据、错误信息等。
    """
    try:
        result = await execution_service.update_execution(
            execution_id=execution_id,
            update_data=execution_update
        )
        if not result:
            raise HTTPException(status_code=404, detail="执行记录不存在")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新执行记录失败: {str(e)}")
        raise HTTPException(status_code=500, detail="更新执行记录失败")

@router.delete("/{execution_id}")
async def delete_execution(execution_id: str):
    """
    删除执行记录

    执行记录删除后，相关结果数据也会被删除。
    """
    try:
        success = await execution_service.delete_execution(execution_id)
        if not success:
            raise HTTPException(status_code=404, detail="执行记录不存在")
        return {"message": "执行记录删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除执行记录失败: {str(e)}")
        raise HTTPException(status_code=500, detail="删除执行记录失败")

@router.get("/", response_model=List[TaskExecutionResponse])
async def list_executions(
    skip: int = Query(0, ge=0, description="跳过数量"),
    limit: int = Query(100, ge=1, le=1000, description="返回数量"),
    task_id: Optional[str] = Query(None, description="任务ID过滤"),
    status: Optional[str] = Query(None, description="状态过滤"),
    agent_type: Optional[str] = Query(None, description="智能体类型过滤"),
    execution_type: Optional[str] = Query(None, description="执行类型过滤"),
    started_after: Optional[str] = Query(None, description="开始时间之后（ISO格式）"),
    started_before: Optional[str] = Query(None, description="开始时间之前（ISO格式）")
):
    """
    列出执行记录

    支持多种过滤条件：任务、状态、智能体类型、时间范围等。
    """
    try:
        executions = await execution_service.list_executions(
            skip=skip,
            limit=limit,
            task_id=task_id,
            status=status,
            agent_type=agent_type,
            execution_type=execution_type,
            started_after=started_after,
            started_before=started_before
        )
        return executions
    except Exception as e:
        logger.error(f"列出执行记录失败: {str(e)}")
        raise HTTPException(status_code=500, detail="列出执行记录失败")

@router.get("/{execution_id}/result", response_model=ExecutionResultResponse)
async def get_execution_result(execution_id: str):
    """
    获取执行结果

    包括执行输出、错误信息、退出码和资源使用详情。
    """
    try:
        result = await execution_service.get_execution_result(execution_id)
        if not result:
            raise HTTPException(status_code=404, detail="执行结果不存在")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取执行结果失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取执行结果失败")

@router.post("/{execution_id}/cancel")
async def cancel_execution(execution_id: str):
    """
    取消正在执行的记录
    """
    try:
        success = await execution_service.cancel_execution(execution_id)
        if not success:
            raise HTTPException(status_code=400, detail="取消执行失败")
        return {"message": "执行已取消"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取消执行失败: {str(e)}")
        raise HTTPException(status_code=500, detail="取消执行失败")

@router.post("/{execution_id}/complete")
async def complete_execution(
    execution_id: str,
    output_data: dict = Body(None, description="输出数据"),
    error_message: Optional[str] = Body(None, description="错误信息"),
    exit_code: Optional[int] = Body(None, description="退出码"),
    resource_usage: Optional[dict] = Body(None, description="资源使用情况")
):
    """
    标记执行记录为完成

    提供执行输出、错误信息和资源使用情况。
    """
    try:
        success = await execution_service.complete_execution(
            execution_id=execution_id,
            output_data=output_data,
            error_message=error_message,
            exit_code=exit_code,
            resource_usage=resource_usage
        )
        if not success:
            raise HTTPException(status_code=400, detail="完成执行失败")
        return {"message": "执行完成"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"完成执行失败: {str(e)}")
        raise HTTPException(status_code=500, detail="完成执行失败")

@router.post("/{execution_id}/fail")
async def fail_execution(
    execution_id: str,
    error_message: str = Body(..., embed=True, description="失败原因")
):
    """
    标记执行记录为失败
    """
    try:
        success = await execution_service.fail_execution(
            execution_id=execution_id,
            error_message=error_message
        )
        if not success:
            raise HTTPException(status_code=400, detail="标记执行失败失败")
        return {"message": "执行标记为失败"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"标记执行失败失败: {str(e)}")
        raise HTTPException(status_code=500, detail="标记执行失败失败")

@router.get("/stats/agent/{agent_type}", response_model=ExecutionStatsResponse)
async def get_agent_execution_stats(
    agent_type: str,
    time_range: Optional[str] = Query("7d", description="时间范围：1d, 7d, 30d, all")
):
    """
    获取智能体执行统计

    按智能体类型统计执行次数、成功率、平均执行时间等。
    """
    try:
        stats = await execution_service.get_agent_execution_stats(
            agent_type=agent_type,
            time_range=time_range
        )
        if not stats:
            raise HTTPException(status_code=404, detail="统计信息不存在")
        return stats
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取智能体执行统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取智能体执行统计失败")

@router.get("/stats/task/{task_id}", response_model=ExecutionStatsResponse)
async def get_task_execution_stats(task_id: str):
    """
    获取任务执行统计

    统计特定任务的所有执行记录。
    """
    try:
        stats = await execution_service.get_task_execution_stats(task_id)
        if not stats:
            raise HTTPException(status_code=404, detail="任务不存在")
        return stats
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务执行统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取任务执行统计失败")

@router.get("/stats/project/{project_id}", response_model=ExecutionStatsResponse)
async def get_project_execution_stats(project_id: str):
    """
    获取项目执行统计

    统计项目下所有任务的执行情况。
    """
    try:
        stats = await execution_service.get_project_execution_stats(project_id)
        if not stats:
            raise HTTPException(status_code=404, detail="项目不存在")
        return stats
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取项目执行统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取项目执行统计失败")

@router.get("/recent/failed", response_model=List[TaskExecutionResponse])
async def list_recent_failed_executions(
    limit: int = Query(10, ge=1, le=100, description="返回数量")
):
    """
    列出最近失败的执行记录

    用于监控和问题排查。
    """
    try:
        executions = await execution_service.list_recent_failed_executions(limit)
        return executions
    except Exception as e:
        logger.error(f"列出最近失败执行记录失败: {str(e)}")
        raise HTTPException(status_code=500, detail="列出最近失败执行记录失败")

@router.get("/recent/long_running", response_model=List[TaskExecutionResponse])
async def list_long_running_executions(
    threshold_minutes: int = Query(30, ge=1, description="阈值（分钟）"),
    limit: int = Query(10, ge=1, le=100, description="返回数量")
):
    """
    列出长时间运行的执行记录

    用于监控可能卡住的任务。
    """
    try:
        executions = await execution_service.list_long_running_executions(
            threshold_minutes=threshold_minutes,
            limit=limit
        )
        return executions
    except Exception as e:
        logger.error(f"列出长时间运行执行记录失败: {str(e)}")
        raise HTTPException(status_code=500, detail="列出长时间运行执行记录失败")