"""智能体协调器

协调多个智能体的执行，提供统一接口和上下文管理。
"""

import asyncio
import loguru
from typing import Dict, Any, Optional, List, Type
from datetime import datetime

from config.agents_config import AGENTS_CONFIG
from core.agents.base_agent import BaseAgent
from core.agents.requirement_agent import RequirementAgent
from core.agents.task_planner import TaskPlannerAgent
from core.agents.development_agent import DevelopmentAgent
from core.agents.review_agent import ReviewAgent
from core.agents.test_agent import TestAgent

logger = loguru.logger


class AgentOrchestrator:
    """智能体协调器"""

    def __init__(self):
        """初始化智能体协调器"""
        self.agents: Dict[str, BaseAgent] = {}
        self.agent_contexts: Dict[str, Dict[str, Any]] = {}
        self.initialized = False

    async def initialize(self):
        """初始化所有智能体"""
        if self.initialized:
            return

        logger.info("初始化智能体协调器...")

        try:
            # 初始化需求智能体
            await self._initialize_requirement_agent()

            # 初始化任务规划智能体
            await self._initialize_task_planner_agent()

            # 初始化开发智能体
            await self._initialize_development_agent()

            # 初始化评审智能体
            await self._initialize_review_agent()

            # 初始化测试智能体
            await self._initialize_test_agent()

            self.initialized = True
            logger.info(f"智能体协调器初始化完成，已注册 {len(self.agents)} 个智能体")

        except Exception as e:
            logger.error(f"智能体协调器初始化失败: {e}")
            raise

    async def _initialize_requirement_agent(self):
        """初始化需求智能体"""
        try:
            if "requirement" in AGENTS_CONFIG:
                agent = RequirementAgent(
                    name="requirement_agent",
                    config=AGENTS_CONFIG["requirement"]
                )
                self.agents["requirement"] = agent
                self.agent_contexts["requirement"] = {
                    "last_used": None,
                    "usage_count": 0,
                    "success_rate": 1.0,
                }
                logger.debug("需求智能体初始化成功")
        except Exception as e:
            logger.error(f"需求智能体初始化失败: {e}")

    async def _initialize_task_planner_agent(self):
        """初始化任务规划智能体"""
        try:
            if "task_planner" in AGENTS_CONFIG:
                agent = TaskPlannerAgent(
                    name="task_planner_agent",
                    config=AGENTS_CONFIG["task_planner"]
                )
                self.agents["task_planner"] = agent
                self.agent_contexts["task_planner"] = {
                    "last_used": None,
                    "usage_count": 0,
                    "success_rate": 1.0,
                }
                logger.debug("任务规划智能体初始化成功")
        except Exception as e:
            logger.error(f"任务规划智能体初始化失败: {e}")

    async def _initialize_development_agent(self):
        """初始化开发智能体"""
        try:
            if "development" in AGENTS_CONFIG:
                # 检查开发智能体是否已实现
                try:
                    from core.agents.development_agent import DevelopmentAgent
                    agent = DevelopmentAgent(
                        name="development_agent",
                        config=AGENTS_CONFIG["development"]
                    )
                    self.agents["development"] = agent
                    self.agent_contexts["development"] = {
                        "last_used": None,
                        "usage_count": 0,
                        "success_rate": 1.0,
                        "preferred_languages": AGENTS_CONFIG["development"].preferred_languages,
                    }
                    logger.debug("开发智能体初始化成功")
                except ImportError:
                    logger.warning("开发智能体未实现，使用占位符")
                    self.agents["development"] = None
        except Exception as e:
            logger.error(f"开发智能体初始化失败: {e}")
            self.agents["development"] = None

    async def _initialize_review_agent(self):
        """初始化评审智能体"""
        try:
            if "review" in AGENTS_CONFIG:
                # 检查评审智能体是否已实现
                try:
                    from core.agents.review_agent import ReviewAgent
                    agent = ReviewAgent(
                        name="review_agent",
                        config=AGENTS_CONFIG["review"]
                    )
                    self.agents["review"] = agent
                    self.agent_contexts["review"] = {
                        "last_used": None,
                        "usage_count": 0,
                        "success_rate": 1.0,
                        "check_security": AGENTS_CONFIG["review"].check_security,
                        "check_performance": AGENTS_CONFIG["review"].check_performance,
                    }
                    logger.debug("评审智能体初始化成功")
                except ImportError:
                    logger.warning("评审智能体未实现，使用占位符")
                    self.agents["review"] = None
        except Exception as e:
            logger.error(f"评审智能体初始化失败: {e}")
            self.agents["review"] = None

    async def _initialize_test_agent(self):
        """初始化测试智能体"""
        try:
            if "test" in AGENTS_CONFIG:
                # 检查测试智能体是否已实现
                try:
                    from core.agents.test_agent import TestAgent
                    agent = TestAgent(
                        name="test_agent",
                        config=AGENTS_CONFIG["test"]
                    )
                    self.agents["test"] = agent
                    self.agent_contexts["test"] = {
                        "last_used": None,
                        "usage_count": 0,
                        "success_rate": 1.0,
                        "test_framework": AGENTS_CONFIG["test"].test_framework,
                    }
                    logger.debug("测试智能体初始化成功")
                except ImportError:
                    logger.warning("测试智能体未实现，使用占位符")
                    self.agents["test"] = None
        except Exception as e:
            logger.error(f"测试智能体初始化失败: {e}")
            self.agents["test"] = None

    async def execute_agent(
        self,
        agent_type: str,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行智能体

        Args:
            agent_type: 智能体类型
            input_data: 输入数据
            context: 执行上下文

        Returns:
            执行结果
        """
        try:
            if not self.initialized:
                await self.initialize()

            if agent_type not in self.agents:
                raise ValueError(f"未知的智能体类型: {agent_type}")

            agent = self.agents[agent_type]
            if agent is None:
                raise ValueError(f"智能体未实现: {agent_type}")

            # 更新智能体上下文
            agent_context = self.agent_contexts[agent_type]
            agent_context["last_used"] = datetime.utcnow().isoformat()
            agent_context["usage_count"] = agent_context.get("usage_count", 0) + 1

            logger.info(f"执行智能体: {agent_type}")

            # 准备输入数据，包含上下文
            enriched_input = {
                **input_data,
                "context": context or {},
                "agent_context": agent_context,
            }

            # 执行智能体
            start_time = datetime.utcnow()
            result = await agent.execute_with_retry(enriched_input)
            execution_time = (datetime.utcnow() - start_time).total_seconds()

            # 更新成功率统计
            if "status" in result and result["status"] == "success":
                agent_context["success_rate"] = (
                    agent_context.get("success_rate", 1.0) * 0.9 + 0.1
                )
            else:
                agent_context["success_rate"] = (
                    agent_context.get("success_rate", 1.0) * 0.9
                )

            # 添加执行元数据
            result["execution_metadata"] = {
                "agent_type": agent_type,
                "execution_time": execution_time,
                "timestamp": datetime.utcnow().isoformat(),
                "usage_count": agent_context["usage_count"],
            }

            logger.info(f"智能体执行完成: {agent_type} (耗时: {execution_time:.2f}秒)")
            return result

        except Exception as e:
            logger.error(f"智能体执行失败: {agent_type} - {e}")

            # 更新成功率统计
            if agent_type in self.agent_contexts:
                self.agent_contexts[agent_type]["success_rate"] = (
                    self.agent_contexts[agent_type].get("success_rate", 1.0) * 0.8
                )

            raise

    async def execute_workflow(
        self,
        workflow_steps: List[Dict[str, Any]],
        initial_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行工作流（多个智能体按顺序执行）

        Args:
            workflow_steps: 工作流步骤定义
            initial_context: 初始上下文

        Returns:
            工作流执行结果
        """
        context = initial_context or {}
        results = {}
        errors = []

        logger.info(f"开始执行工作流，共 {len(workflow_steps)} 个步骤")

        for step_index, step in enumerate(workflow_steps):
            step_name = step.get("name", f"step_{step_index}")
            agent_type = step.get("agent_type")
            step_input = step.get("input", {})

            try:
                logger.info(f"执行工作流步骤 {step_index + 1}/{len(workflow_steps)}: {step_name} ({agent_type})")

                # 动态解析输入（支持从上下文或之前的结果中引用）
                resolved_input = self._resolve_step_input(step_input, context, results)

                # 执行智能体
                result = await self.execute_agent(
                    agent_type=agent_type,
                    input_data=resolved_input,
                    context=context
                )

                # 保存步骤结果
                results[step_name] = {
                    "status": "success",
                    "result": result,
                    "step_index": step_index,
                }

                # 更新上下文
                context = self._update_context_from_result(context, result, step.get("context_updates", {}))

                # 检查是否需要停止
                if step.get("stop_on_failure") and result.get("status") != "success":
                    logger.warning(f"工作流步骤 {step_name} 失败，停止工作流")
                    break

            except Exception as e:
                logger.error(f"工作流步骤 {step_name} 执行失败: {e}")

                errors.append({
                    "step": step_name,
                    "step_index": step_index,
                    "agent_type": agent_type,
                    "error": str(e),
                })

                results[step_name] = {
                    "status": "failed",
                    "error": str(e),
                    "step_index": step_index,
                }

                # 检查是否需要停止
                if step.get("stop_on_failure", True):
                    logger.warning(f"工作流步骤 {step_name} 失败，停止工作流")
                    break

        # 准备最终结果
        success_count = sum(1 for r in results.values() if r.get("status") == "success")
        failed_count = len(results) - success_count

        return {
            "workflow_status": "completed" if failed_count == 0 else "partial",
            "success_steps": success_count,
            "failed_steps": failed_count,
            "total_steps": len(workflow_steps),
            "results": results,
            "errors": errors,
            "final_context": context,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _resolve_step_input(
        self,
        step_input: Dict[str, Any],
        context: Dict[str, Any],
        previous_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """解析步骤输入，支持变量引用"""
        import copy

        resolved_input = copy.deepcopy(step_input)

        # 递归解析输入中的变量引用
        def resolve_value(value):
            if isinstance(value, str) and value.startswith("$"):
                # 变量引用格式: $context.key 或 $results.step_name.key
                if value.startswith("$context."):
                    path = value[9:]  # 去掉 "$context."
                    return self._get_nested_value(context, path)
                elif value.startswith("$results."):
                    path = value[9:]  # 去掉 "$results."
                    parts = path.split(".", 1)
                    if len(parts) == 2:
                        step_name, key_path = parts
                        if step_name in previous_results:
                            return self._get_nested_value(previous_results[step_name], key_path)
                    return None
                elif value.startswith("$env."):
                    # 环境变量引用（简化版本）
                    import os
                    env_key = value[5:]  # 去掉 "$env."
                    return os.getenv(env_key, "")
            elif isinstance(value, dict):
                return {k: resolve_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [resolve_value(v) for v in value]
            else:
                return value

        return resolve_value(resolved_input)

    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """获取嵌套字典中的值"""
        keys = path.split(".")
        current = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current

    def _update_context_from_result(
        self,
        context: Dict[str, Any],
        result: Dict[str, Any],
        context_updates: Dict[str, str]
    ) -> Dict[str, Any]:
        """根据执行结果更新上下文"""
        updated_context = context.copy()

        for context_key, result_path in context_updates.items():
            value = self._get_nested_value(result, result_path)
            if value is not None:
                # 支持嵌套键路径
                keys = context_key.split(".")
                current = updated_context
                for key in keys[:-1]:
                    if key not in current:
                        current[key] = {}
                    current = current[key]
                current[keys[-1]] = value

        return updated_context

    async def get_agent_status(self, agent_type: Optional[str] = None) -> Dict[str, Any]:
        """
        获取智能体状态

        Args:
            agent_type: 智能体类型，如果为None则返回所有智能体状态

        Returns:
            智能体状态信息
        """
        if not self.initialized:
            await self.initialize()

        if agent_type:
            if agent_type not in self.agents:
                raise ValueError(f"未知的智能体类型: {agent_type}")

            agent = self.agents[agent_type]
            agent_context = self.agent_contexts.get(agent_type, {})

            return {
                "agent_type": agent_type,
                "available": agent is not None,
                "context": agent_context,
                "agent_status": agent.get_status() if agent else None,
            }
        else:
            status = {}
            for agent_type, agent in self.agents.items():
                agent_context = self.agent_contexts.get(agent_type, {})
                status[agent_type] = {
                    "available": agent is not None,
                    "context": agent_context,
                    "agent_status": agent.get_status() if agent else None,
                }
            return status

    async def reset_agent_context(self, agent_type: str) -> bool:
        """
        重置智能体上下文

        Args:
            agent_type: 智能体类型

        Returns:
            是否成功
        """
        if agent_type not in self.agent_contexts:
            return False

        # 重置上下文
        self.agent_contexts[agent_type] = {
            "last_used": None,
            "usage_count": 0,
            "success_rate": 1.0,
        }

        # 重置智能体特定的上下文
        if agent_type == "development":
            self.agent_contexts[agent_type]["preferred_languages"] = (
                AGENTS_CONFIG["development"].preferred_languages
                if "development" in AGENTS_CONFIG else []
            )
        elif agent_type == "review":
            self.agent_contexts[agent_type].update({
                "check_security": AGENTS_CONFIG["review"].check_security,
                "check_performance": AGENTS_CONFIG["review"].check_performance,
            } if "review" in AGENTS_CONFIG else {})
        elif agent_type == "test":
            self.agent_contexts[agent_type]["test_framework"] = (
                AGENTS_CONFIG["test"].test_framework
                if "test" in AGENTS_CONFIG else "pytest"
            )

        logger.info(f"智能体上下文已重置: {agent_type}")
        return True

# 全局智能体协调器实例
_agent_orchestrator = None

async def get_agent_orchestrator() -> AgentOrchestrator:
    """
    获取智能体协调器实例（单例模式）

    Returns:
        智能体协调器实例
    """
    global _agent_orchestrator
    if _agent_orchestrator is None:
        _agent_orchestrator = AgentOrchestrator()
        await _agent_orchestrator.initialize()
    return _agent_orchestrator