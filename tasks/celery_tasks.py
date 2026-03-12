"""Celery任务定义

定义所有后台任务，包括工作流执行、任务处理、监控等。
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import loguru
from celery import Task
from sqlalchemy.ext.asyncio import AsyncSession

from config.celery_config import app
from models.database import (
    get_async_session,
    Task as TaskModel,
    TaskExecution as TaskExecutionModel,
    Requirement as RequirementModel,
    Project as ProjectModel,
    User as UserModel,
    CodeArtifact as CodeArtifactModel,
    ReviewFeedback as ReviewFeedbackModel,
    TestResult as TestResultModel,
)
from services.task_service import TaskService
from services.execution_service import ExecutionService
from core.agents.requirement_agent import RequirementAgent
from core.agents.task_planner import TaskPlannerAgent
from config.agents_config import AGENTS_CONFIG

logger = loguru.logger

class BaseCeleryTask(Task):
    """Celery任务基类，提供通用功能"""

    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """任务失败时的处理"""
        logger.error(f"任务 {task_id} 失败: {exc}", exc_info=einfo)

    def on_success(self, retval, task_id, args, kwargs):
        """任务成功时的处理"""
        logger.info(f"任务 {task_id} 成功完成")

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """任务重试时的处理"""
        logger.warning(f"任务 {task_id} 重试中: {exc}")


@app.task(base=BaseCeleryTask, bind=True, max_retries=3)
def process_requirement_analysis(self, requirement_id: str) -> Dict[str, Any]:
    """
    处理需求分析任务

    Args:
        requirement_id: 需求ID

    Returns:
        分析结果
    """
    try:
        # 由于Celery任务不能直接运行async函数，需要创建新事件循环
        async def async_process():
            async with get_async_session() as session:
                # 获取需求
                requirement = await session.get(RequirementModel, requirement_id)
                if not requirement:
                    raise ValueError(f"需求不存在: {requirement_id}")

                # 更新需求状态为分析中
                requirement.status = 'analyzing'
                await session.commit()

                # 初始化需求智能体
                requirement_agent = RequirementAgent(
                    name="requirement_analyzer",
                    config=AGENTS_CONFIG["requirement"]
                )

                # 准备输入数据
                input_data = {
                    "requirement_id": requirement_id,
                    "document_content": requirement.description or "",
                    "document_path": requirement.document_path,
                    "project_id": requirement.project_id,
                }

                # 执行需求分析
                analysis_result = await requirement_agent.execute_with_retry(input_data)

                # 更新需求分析结果
                requirement.analysis_result = analysis_result
                requirement.status = 'analyzed'
                requirement.updated_at = datetime.utcnow()
                await session.commit()

                # 触发任务规划
                task_planning_task.delay(requirement_id)

                return {
                    "requirement_id": requirement_id,
                    "analysis_result": analysis_result,
                    "status": "completed"
                }

        # 运行异步函数
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(async_process())
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"需求分析失败: {e}")

        # 更新需求状态为失败
        async def update_failed_status():
            async with get_async_session() as session:
                requirement = await session.get(RequirementModel, requirement_id)
                if requirement:
                    requirement.status = 'failed'
                    await session.commit()

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(update_failed_status())
        except Exception as update_error:
            logger.error(f"更新需求状态失败: {update_error}")

        # 重试或抛出异常
        raise self.retry(exc=e, countdown=60)


@app.task(base=BaseCeleryTask, bind=True, max_retries=3)
def task_planning_task(self, requirement_id: str) -> Dict[str, Any]:
    """
    任务规划任务

    Args:
        requirement_id: 需求ID

    Returns:
        规划结果
    """
    try:
        async def async_process():
            async with get_async_session() as session:
                # 获取需求及其分析结果
                requirement = await session.get(RequirementModel, requirement_id)
                if not requirement or not requirement.analysis_result:
                    raise ValueError(f"需求不存在或未分析: {requirement_id}")

                # 初始化任务规划智能体
                task_planner = TaskPlannerAgent(
                    name="task_planner",
                    config=AGENTS_CONFIG["task_planner"]
                )

                # 准备输入数据
                input_data = {
                    "requirement_spec": requirement.analysis_result,
                    "project_id": requirement.project_id,
                    "requirement_id": requirement_id,
                }

                # 执行任务规划
                planning_result = await task_planner.execute_with_retry(input_data)

                # 创建任务
                task_service = TaskService()
                created_tasks = []

                for task_data in planning_result.get("tasks", []):
                    # 转换任务数据格式
                    task_create_data = {
                        "project_id": requirement.project_id,
                        "requirement_id": requirement_id,
                        "title": task_data.get("title", "未命名任务"),
                        "description": task_data.get("description", ""),
                        "task_type": task_data.get("type", "development"),
                        "priority": task_data.get("priority", "medium"),
                        "estimated_hours": task_data.get("estimated_hours", 1.0),
                        "metadata": {
                            "dependencies": task_data.get("dependencies", []),
                            "skills_required": task_data.get("skills_required", []),
                        }
                    }

                    # 创建任务
                    created_task = await task_service.create_task(task_create_data)
                    created_tasks.append(created_task)

                    # 触发任务执行（如果是独立任务）
                    if not task_data.get("dependencies"):
                        execute_standard_workflow.delay(created_task.id)

                return {
                    "requirement_id": requirement_id,
                    "planned_tasks": len(created_tasks),
                    "task_ids": [task.id for task in created_tasks],
                    "status": "completed"
                }

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(async_process())
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"任务规划失败: {e}")
        raise self.retry(exc=e, countdown=60)


@app.task(base=BaseCeleryTask, bind=True, max_retries=3)
def execute_high_priority_workflow(self, task_id: str) -> Dict[str, Any]:
    """
    执行高优先级工作流

    Args:
        task_id: 任务ID

    Returns:
        执行结果
    """
    logger.info(f"执行高优先级工作流: {task_id}")
    return {"task_id": task_id, "status": "started", "priority": "high"}


@app.task(base=BaseCeleryTask, bind=True, max_retries=3)
def execute_standard_workflow(self, task_id: str) -> Dict[str, Any]:
    """
    执行标准工作流

    Args:
        task_id: 任务ID

    Returns:
        执行结果
    """
    try:
        async def async_process():
            async with get_async_session() as session:
                # 获取任务
                task = await session.get(TaskModel, task_id)
                if not task:
                    raise ValueError(f"任务不存在: {task_id}")

                # 更新任务状态为进行中
                task.status = 'in_progress'
                task.started_at = datetime.utcnow()
                await session.commit()

                # 创建执行记录
                execution = TaskExecutionModel(
                    task_id=task_id,
                    execution_type='auto',
                    status='running',
                    agent_type=task.task_type,
                    input_data={"task_id": task_id},
                    started_at=datetime.utcnow(),
                )
                session.add(execution)
                await session.commit()

                # 根据任务类型执行不同工作流
                if task.task_type == 'development':
                    result = await execute_development_workflow(task, execution)
                elif task.task_type == 'review':
                    result = await execute_review_workflow(task, execution)
                elif task.task_type == 'test':
                    result = await execute_test_workflow(task, execution)
                else:
                    result = {"status": "skipped", "reason": f"不支持的任务类型: {task.task_type}"}

                # 更新执行记录
                execution.status = 'completed' if result.get('status') == 'success' else 'failed'
                execution.output_data = result
                execution.completed_at = datetime.utcnow()
                execution.execution_time = (datetime.utcnow() - execution.started_at).total_seconds()
                await session.commit()

                # 更新任务状态
                if execution.status == 'completed':
                    task.status = 'completed'
                    task.completed_at = datetime.utcnow()
                    task.actual_hours = execution.execution_time / 3600  # 转换为小时
                else:
                    task.status = 'failed'

                await session.commit()

                return {
                    "task_id": task_id,
                    "execution_id": execution.id,
                    "status": execution.status,
                    "result": result,
                }

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(async_process())
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"标准工作流执行失败: {e}")

        # 更新任务状态为失败
        async def update_failed_status():
            async with get_async_session() as session:
                task = await session.get(TaskModel, task_id)
                if task:
                    task.status = 'failed'
                    await session.commit()

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(update_failed_status())
        except Exception as update_error:
            logger.error(f"更新任务状态失败: {update_error}")

        raise self.retry(exc=e, countdown=60)


async def execute_development_workflow(task: TaskModel, execution: TaskExecutionModel) -> Dict[str, Any]:
    """执行开发工作流"""
    # TODO: 实现开发智能体集成
    logger.info(f"执行开发工作流: {task.id}")

    # 模拟开发过程
    await asyncio.sleep(2)

    return {
        "status": "success",
        "code_generated": True,
        "files": ["main.py", "utils.py"],
        "language": "python",
    }


async def execute_review_workflow(task: TaskModel, execution: TaskExecutionModel) -> Dict[str, Any]:
    """执行评审工作流"""
    # TODO: 实现评审智能体集成
    logger.info(f"执行评审工作流: {task.id}")

    # 模拟评审过程
    await asyncio.sleep(1)

    return {
        "status": "success",
        "review_passed": True,
        "score": 85.5,
        "issues_found": 3,
        "suggestions": ["添加注释", "优化性能", "改进错误处理"],
    }


async def execute_test_workflow(task: TaskModel, execution: TaskExecutionModel) -> Dict[str, Any]:
    """执行测试工作流"""
    # TODO: 实现测试智能体集成
    logger.info(f"执行测试工作流: {task.id}")

    # 模拟测试过程
    await asyncio.sleep(1.5)

    return {
        "status": "success",
        "tests_passed": True,
        "coverage": 92.3,
        "tests_run": 15,
        "failures": 0,
    }


@app.task(base=BaseCeleryTask, bind=True, max_retries=2)
def execute_background_workflow(self, workflow_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    执行后台工作流

    Args:
        workflow_type: 工作流类型
        data: 工作流数据

    Returns:
        执行结果
    """
    logger.info(f"执行后台工作流: {workflow_type}")
    # TODO: 实现具体后台工作流
    return {"workflow_type": workflow_type, "status": "completed", "data": data}


@app.task(base=BaseCeleryTask)
def check_pending_tasks() -> Dict[str, Any]:
    """
    检查待处理任务

    Returns:
        检查结果
    """
    try:
        async def async_check():
            async with get_async_session() as session:
                # 查询待处理任务
                from sqlalchemy import select
                stmt = select(TaskModel).where(
                    TaskModel.status.in_(['pending', 'blocked'])
                )
                result = await session.execute(stmt)
                pending_tasks = result.scalars().all()

                # 查询进行中任务
                stmt = select(TaskModel).where(TaskModel.status == 'in_progress')
                result = await session.execute(stmt)
                in_progress_tasks = result.scalars().all()

                return {
                    "pending_tasks": len(pending_tasks),
                    "in_progress_tasks": len(in_progress_tasks),
                    "timestamp": datetime.utcnow().isoformat(),
                }

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(async_check())
            logger.info(f"待处理任务检查完成: {result}")
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"检查待处理任务失败: {e}")
        return {"error": str(e), "status": "failed"}


@app.task(base=BaseCeleryTask)
def cleanup_old_tasks() -> Dict[str, Any]:
    """
    清理旧任务

    Returns:
        清理结果
    """
    try:
        async def async_cleanup():
            async with get_async_session() as session:
                # 计算30天前的日期
                cutoff_date = datetime.utcnow() - timedelta(days=30)

                # 查询30天前完成的旧任务
                from sqlalchemy import select, and_, or_
                stmt = select(TaskModel).where(
                    and_(
                        or_(TaskModel.status == 'completed', TaskModel.status == 'failed'),
                        TaskModel.completed_at < cutoff_date
                    )
                )
                result = await session.execute(stmt)
                old_tasks = result.scalars().all()

                # 记录但不实际删除（可以后续实现归档功能）
                old_task_ids = [task.id for task in old_tasks]

                return {
                    "old_tasks_found": len(old_tasks),
                    "old_task_ids": old_task_ids,
                    "cutoff_date": cutoff_date.isoformat(),
                }

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(async_cleanup())
            logger.info(f"清理旧任务完成: 找到 {result['old_tasks_found']} 个旧任务")
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"清理旧任务失败: {e}")
        return {"error": str(e), "status": "failed"}


@app.task(base=BaseCeleryTask)
def monitor_workflows() -> Dict[str, Any]:
    """
    监控工作流状态

    Returns:
        监控结果
    """
    try:
        async def async_monitor():
            async with get_async_session() as session:
                # 查询最近24小时的工作流执行情况
                from sqlalchemy import select, func
                start_time = datetime.utcnow() - timedelta(hours=24)

                # 按状态统计执行
                stmt = select(
                    TaskExecutionModel.status,
                    func.count(TaskExecutionModel.id).label('count')
                ).where(
                    TaskExecutionModel.started_at >= start_time
                ).group_by(TaskExecutionModel.status)

                result = await session.execute(stmt)
                status_stats = {row[0]: row[1] for row in result}

                # 计算成功率
                total = sum(status_stats.values())
                success_count = status_stats.get('completed', 0)
                success_rate = (success_count / total * 100) if total > 0 else 0

                return {
                    "monitoring_period": "24h",
                    "start_time": start_time.isoformat(),
                    "status_stats": status_stats,
                    "total_executions": total,
                    "success_rate": round(success_rate, 2),
                    "timestamp": datetime.utcnow().isoformat(),
                }

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(async_monitor())
            logger.info(f"工作流监控完成: 成功率 {result['success_rate']}%")
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"工作流监控失败: {e}")
        return {"error": str(e), "status": "failed"}


@app.task(base=BaseCeleryTask, bind=True, max_retries=3)
def process_task_execution(self, execution_id: str) -> Dict[str, Any]:
    """
    处理任务执行

    Args:
        execution_id: 执行记录ID

    Returns:
        执行结果
    """
    logger.info(f"处理任务执行: {execution_id}")
    # TODO: 实现具体的任务执行处理
    return {"execution_id": execution_id, "status": "processed"}