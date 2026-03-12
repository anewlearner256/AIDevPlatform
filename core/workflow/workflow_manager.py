"""工作流管理器

基于LangGraph的工作流管理和执行引擎。
"""

import asyncio
import json
import uuid
import loguru
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List, Type, Callable
from dataclasses import dataclass, field

from langgraph.graph import StateGraph, END
from langgraph.checkpoint import MemorySaver
from langgraph.graph.message import add_messages

from config.settings import settings
from core.agents.agent_orchestrator import AgentOrchestrator
from core.agents.base_agent import BaseAgent
from models.database import get_async_session
from models.database import (
    WorkflowState as WorkflowStateModel,
    WorkflowExecution as WorkflowExecutionModel,
)

logger = loguru.logger


class WorkflowType(Enum):
    """工作流类型"""
    DEVELOPMENT = "development"
    REVIEW = "review"
    TEST = "test"
    FULL_DEVELOPMENT = "full_development"
    REQUIREMENT_ANALYSIS = "requirement_analysis"
    TASK_PLANNING = "task_planning"


class WorkflowStatus(Enum):
    """工作流状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


@dataclass
class WorkflowState:
    """工作流状态数据类"""
    # 工作流基本信息
    workflow_id: str
    workflow_type: str
    status: str = WorkflowStatus.PENDING.value

    # 输入输出数据
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    intermediate_results: Dict[str, Any] = field(default_factory=dict)

    # 执行上下文
    current_step: str = "start"
    step_history: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)

    # 智能体执行上下文
    agent_results: Dict[str, Any] = field(default_factory=dict)
    code_artifacts: Dict[str, Any] = field(default_factory=dict)
    review_feedback: Dict[str, Any] = field(default_factory=dict)
    test_results: Dict[str, Any] = field(default_factory=dict)

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class WorkflowManager:
    """工作流管理器"""

    def __init__(self, agent_orchestrator: Optional[AgentOrchestrator] = None):
        """
        初始化工作流管理器

        Args:
            agent_orchestrator: 智能体协调器实例
        """
        self.agent_orchestrator = agent_orchestrator or AgentOrchestrator()
        self.workflow_graphs: Dict[str, StateGraph] = {}
        self.checkpointer = MemorySaver()

    async def initialize(self):
        """初始化工作流管理器"""
        logger.info("初始化工作流管理器...")

        # 初始化智能体协调器
        await self.agent_orchestrator.initialize()

        # 注册工作流
        await self._register_workflows()

        logger.info("工作流管理器初始化完成")

    async def _register_workflows(self):
        """注册工作流定义"""
        from .graph_definitions import (
            DevelopmentWorkflow,
            ReviewWorkflow,
            TestWorkflow,
            FullDevelopmentWorkflow,
        )

        # 注册开发工作流
        dev_workflow = DevelopmentWorkflow(self.agent_orchestrator)
        self.workflow_graphs[WorkflowType.DEVELOPMENT.value] = dev_workflow.get_graph()

        # 注册评审工作流
        review_workflow = ReviewWorkflow(self.agent_orchestrator)
        self.workflow_graphs[WorkflowType.REVIEW.value] = review_workflow.get_graph()

        # 注册测试工作流
        test_workflow = TestWorkflow(self.agent_orchestrator)
        self.workflow_graphs[WorkflowType.TEST.value] = test_workflow.get_graph()

        # 注册完整开发工作流
        full_workflow = FullDevelopmentWorkflow(self.agent_orchestrator)
        self.workflow_graphs[WorkflowType.FULL_DEVELOPMENT.value] = full_workflow.get_graph()

        logger.info(f"已注册 {len(self.workflow_graphs)} 个工作流")

    async def execute_workflow(
        self,
        workflow_type: Union[str, WorkflowType],
        input_data: Dict[str, Any],
        workflow_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行工作流

        Args:
            workflow_type: 工作流类型
            input_data: 输入数据
            workflow_id: 工作流ID（如果为None则自动生成）
            config: 工作流配置

        Returns:
            执行结果
        """
        workflow_id = workflow_id or str(uuid.uuid4())
        workflow_type_str = workflow_type.value if isinstance(workflow_type, WorkflowType) else workflow_type

        try:
            # 创建工作流状态记录
            workflow_state = WorkflowState(
                workflow_id=workflow_id,
                workflow_type=workflow_type_str,
                status=WorkflowStatus.RUNNING.value,
                input_data=input_data,
                metadata=config or {},
            )

            # 保存初始状态到数据库
            execution_id = await self._save_workflow_state(workflow_state)

            logger.info(f"开始执行工作流: {workflow_id} ({workflow_type_str})")

            # 获取工作流图
            if workflow_type_str not in self.workflow_graphs:
                raise ValueError(f"未知的工作流类型: {workflow_type_str}")

            graph = self.workflow_graphs[workflow_type_str]

            # 准备初始状态
            initial_state = {
                "workflow_state": workflow_state,
                "input_data": input_data,
                "current_step": "start",
                "errors": [],
            }

            # 执行工作流
            try:
                # 使用LangGraph执行工作流
                final_state = await self._execute_langraph_workflow(
                    graph=graph,
                    initial_state=initial_state,
                    config=config or {},
                    workflow_id=workflow_id,
                )

                # 提取结果
                result_state = final_state.get("workflow_state", workflow_state)
                result_state.status = WorkflowStatus.COMPLETED.value
                result_state.updated_at = datetime.utcnow()

                # 更新数据库记录
                await self._update_workflow_execution(
                    execution_id=execution_id,
                    state=result_state,
                    status=WorkflowStatus.COMPLETED.value,
                )

                logger.info(f"工作流执行完成: {workflow_id}")

                return {
                    "workflow_id": workflow_id,
                    "execution_id": execution_id,
                    "status": "completed",
                    "result": result_state.output_data,
                    "intermediate_results": result_state.intermediate_results,
                    "metadata": result_state.metadata,
                }

            except Exception as e:
                logger.error(f"工作流执行失败: {e}")

                # 更新状态为失败
                workflow_state.status = WorkflowStatus.FAILED.value
                workflow_state.errors.append({
                    "step": workflow_state.current_step,
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat(),
                })
                workflow_state.updated_at = datetime.utcnow()

                await self._update_workflow_execution(
                    execution_id=execution_id,
                    state=workflow_state,
                    status=WorkflowStatus.FAILED.value,
                    error=str(e),
                )

                raise

        except Exception as e:
            logger.error(f"工作流执行过程中发生错误: {e}")
            raise

    async def _execute_langraph_workflow(
        self,
        graph: StateGraph,
        initial_state: Dict[str, Any],
        config: Dict[str, Any],
        workflow_id: str
    ) -> Dict[str, Any]:
        """
        执行LangGraph工作流

        Args:
            graph: LangGraph图
            initial_state: 初始状态
            config: 配置
            workflow_id: 工作流ID

        Returns:
            最终状态
        """
        try:
            # 配置检查点
            checkpointer_config = {
                "configurable": {
                    "thread_id": workflow_id,
                }
            }

            # 同步执行工作流（LangGraph目前主要支持同步API）
            # 注意：在实际使用时，可能需要根据LangGraph版本调整
            app = graph.compile(checkpointer=self.checkpointer)

            # 执行工作流
            final_state = app.invoke(
                initial_state,
                config=checkpointer_config,
            )

            return final_state

        except Exception as e:
            logger.error(f"LangGraph工作流执行失败: {e}")
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
            async with get_async_session() as session:
                # 查询工作流执行记录
                execution = await session.get(WorkflowExecutionModel, workflow_id)
                if not execution:
                    return None

                # 查询关联的工作流状态
                state = await session.get(WorkflowStateModel, execution.state_id)

                return {
                    "workflow_id": execution.workflow_id,
                    "execution_id": execution.id,
                    "status": execution.status,
                    "workflow_type": execution.workflow_type,
                    "state": state.state_data if state else {},
                    "created_at": execution.created_at.isoformat(),
                    "started_at": execution.started_at.isoformat() if execution.started_at else None,
                    "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                    "error": execution.error_message,
                    "metadata": execution.metadata,
                }

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
            async with get_async_session() as session:
                execution = await session.get(WorkflowExecutionModel, workflow_id)
                if not execution:
                    return False

                execution.status = WorkflowStatus.PAUSED.value
                execution.updated_at = datetime.utcnow()
                await session.commit()

                logger.info(f"工作流已暂停: {workflow_id}")
                return True

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
            async with get_async_session() as session:
                execution = await session.get(WorkflowExecutionModel, workflow_id)
                if not execution or execution.status != WorkflowStatus.PAUSED.value:
                    return False

                execution.status = WorkflowStatus.RUNNING.value
                execution.updated_at = datetime.utcnow()
                await session.commit()

                logger.info(f"工作流已恢复: {workflow_id}")
                return True

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
            async with get_async_session() as session:
                execution = await session.get(WorkflowExecutionModel, workflow_id)
                if not execution:
                    return False

                execution.status = WorkflowStatus.CANCELLED.value
                execution.completed_at = datetime.utcnow()
                execution.updated_at = datetime.utcnow()
                await session.commit()

                logger.info(f"工作流已取消: {workflow_id}")
                return True

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
            async with get_async_session() as session:
                from sqlalchemy import select

                # 查询该工作流的所有执行记录
                stmt = select(WorkflowExecutionModel).where(
                    WorkflowExecutionModel.workflow_id == workflow_id
                ).order_by(WorkflowExecutionModel.created_at.desc())

                result = await session.execute(stmt)
                executions = result.scalars().all()

                history = []
                for execution in executions:
                    history.append({
                        "execution_id": execution.id,
                        "status": execution.status,
                        "created_at": execution.created_at.isoformat(),
                        "started_at": execution.started_at.isoformat() if execution.started_at else None,
                        "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                        "error": execution.error_message,
                        "metadata": execution.metadata,
                    })

                return history

        except Exception as e:
            logger.error(f"获取工作流历史失败: {e}")
            return []

    async def _save_workflow_state(self, state: WorkflowState) -> str:
        """
        保存工作流状态到数据库

        Args:
            state: 工作流状态

        Returns:
            执行记录ID
        """
        try:
            async with get_async_session() as session:
                # 创建工作流状态记录
                workflow_state = WorkflowStateModel(
                    id=str(uuid.uuid4()),
                    state_data=state.__dict__,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                session.add(workflow_state)

                # 创建工作流执行记录
                execution = WorkflowExecutionModel(
                    id=str(uuid.uuid4()),
                    workflow_id=state.workflow_id,
                    workflow_type=state.workflow_type,
                    state_id=workflow_state.id,
                    status=state.status,
                    input_data=state.input_data,
                    metadata=state.metadata,
                    created_at=datetime.utcnow(),
                    started_at=datetime.utcnow(),
                )
                session.add(execution)

                await session.commit()

                return execution.id

        except Exception as e:
            logger.error(f"保存工作流状态失败: {e}")
            raise

    async def _update_workflow_execution(
        self,
        execution_id: str,
        state: WorkflowState,
        status: str,
        error: Optional[str] = None
    ):
        """
        更新工作流执行记录

        Args:
            execution_id: 执行记录ID
            state: 工作流状态
            status: 新状态
            error: 错误信息
        """
        try:
            async with get_async_session() as session:
                # 更新执行记录
                execution = await session.get(WorkflowExecutionModel, execution_id)
                if not execution:
                    return

                execution.status = status
                execution.output_data = state.output_data
                execution.error_message = error
                execution.completed_at = datetime.utcnow() if status in [WorkflowStatus.COMPLETED.value, WorkflowStatus.FAILED.value, WorkflowStatus.CANCELLED.value] else None
                execution.updated_at = datetime.utcnow()

                # 更新状态记录
                workflow_state = await session.get(WorkflowStateModel, execution.state_id)
                if workflow_state:
                    workflow_state.state_data = state.__dict__
                    workflow_state.updated_at = datetime.utcnow()

                await session.commit()

        except Exception as e:
            logger.error(f"更新工作流执行记录失败: {e}")
            raise

    async def cleanup_old_workflows(self, days: int = 30):
        """
        清理旧的工作流记录

        Args:
            days: 清理多少天前的记录
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            async with get_async_session() as session:
                from sqlalchemy import select, delete

                # 查找需要清理的执行记录
                stmt = select(WorkflowExecutionModel.id).where(
                    WorkflowExecutionModel.created_at < cutoff_date,
                    WorkflowExecutionModel.status.in_([
                        WorkflowStatus.COMPLETED.value,
                        WorkflowStatus.FAILED.value,
                        WorkflowStatus.CANCELLED.value,
                    ])
                )

                result = await session.execute(stmt)
                old_execution_ids = result.scalars().all()

                # 删除关联的状态记录和执行记录
                deleted_count = 0
                for execution_id in old_execution_ids:
                    execution = await session.get(WorkflowExecutionModel, execution_id)
                    if execution:
                        # 删除状态记录
                        if execution.state_id:
                            await session.delete(await session.get(WorkflowStateModel, execution.state_id))

                        # 删除执行记录
                        await session.delete(execution)
                        deleted_count += 1

                await session.commit()
                logger.info(f"清理旧工作流记录完成: 删除了 {deleted_count} 条记录")

                return deleted_count

        except Exception as e:
            logger.error(f"清理旧工作流记录失败: {e}")
            return 0

# 全局工作流管理器实例
_workflow_manager = None

async def get_workflow_manager() -> WorkflowManager:
    """
    获取工作流管理器实例（单例模式）

    Returns:
        工作流管理器实例
    """
    global _workflow_manager
    if _workflow_manager is None:
        _workflow_manager = WorkflowManager()
        await _workflow_manager.initialize()
    return _workflow_manager