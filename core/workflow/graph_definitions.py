"""工作流图定义

基于LangGraph定义各种工作流图。
"""

from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from core.agents.agent_orchestrator import AgentOrchestrator
from core.workflow.workflow_manager import WorkflowState


class BaseWorkflow:
    """基础工作流类"""

    def __init__(self, agent_orchestrator: AgentOrchestrator):
        """
        初始化工作流

        Args:
            agent_orchestrator: 智能体协调器
        """
        self.agent_orchestrator = agent_orchestrator
        self.graph = StateGraph(WorkflowState)

    def get_graph(self) -> StateGraph:
        """获取工作流图"""
        return self.graph.compile()


class DevelopmentWorkflow(BaseWorkflow):
    """开发工作流"""

    def __init__(self, agent_orchestrator: AgentOrchestrator):
        super().__init__(agent_orchestrator)
        self._build_graph()

    def _build_graph(self):
        """构建开发工作流图"""

        # 定义节点
        self.graph.add_node("start", self._start_node)
        self.graph.add_node("analyze_requirements", self._analyze_requirements_node)
        self.graph.add_node("design_solution", self._design_solution_node)
        self.graph.add_node("generate_code", self._generate_code_node)
        self.graph.add_node("review_code", self._review_code_node)
        self.graph.add_node("finalize", self._finalize_node)
        self.graph.add_node("handle_error", self._handle_error_node)

        # 定义边
        self.graph.set_entry_point("start")
        self.graph.add_edge("start", "analyze_requirements")
        self.graph.add_edge("analyze_requirements", "design_solution")
        self.graph.add_edge("design_solution", "generate_code")
        self.graph.add_conditional_edges(
            "generate_code",
            self._check_code_quality,
            {
                "needs_review": "review_code",
                "good_quality": "finalize",
                "error": "handle_error",
            }
        )
        self.graph.add_edge("review_code", "finalize")
        self.graph.add_edge("handle_error", END)
        self.graph.add_edge("finalize", END)

    async def _start_node(self, state: WorkflowState) -> Dict[str, Any]:
        """开始节点"""
        state.current_step = "start"
        state.step_history.append({
            "step": "start",
            "timestamp": state.updated_at.isoformat(),
            "status": "started",
        })
        return {"workflow_state": state}

    async def _analyze_requirements_node(self, state: WorkflowState) -> Dict[str, Any]:
        """分析需求节点"""
        try:
            state.current_step = "analyze_requirements"

            # 执行需求分析
            result = await self.agent_orchestrator.execute_agent(
                agent_type="requirement",
                input_data=state.input_data.get("requirement_data", {}),
                context=state.intermediate_results
            )

            # 保存结果
            state.intermediate_results["requirement_analysis"] = result
            state.step_history.append({
                "step": "analyze_requirements",
                "timestamp": state.updated_at.isoformat(),
                "status": "completed",
                "result": result.get("status", "unknown"),
            })

            return {"workflow_state": state}

        except Exception as e:
            state.errors.append({
                "step": "analyze_requirements",
                "error": str(e),
                "timestamp": state.updated_at.isoformat(),
            })
            raise

    async def _design_solution_node(self, state: WorkflowState) -> Dict[str, Any]:
        """设计方案节点"""
        try:
            state.current_step = "design_solution"

            # 获取需求分析结果
            requirement_analysis = state.intermediate_results.get("requirement_analysis", {})

            # 执行任务规划
            result = await self.agent_orchestrator.execute_agent(
                agent_type="task_planner",
                input_data={
                    "requirement_spec": requirement_analysis,
                    "project_context": state.input_data.get("project_context", {}),
                },
                context=state.intermediate_results
            )

            # 保存结果
            state.intermediate_results["solution_design"] = result
            state.step_history.append({
                "step": "design_solution",
                "timestamp": state.updated_at.isoformat(),
                "status": "completed",
                "result": result.get("status", "unknown"),
            })

            return {"workflow_state": state}

        except Exception as e:
            state.errors.append({
                "step": "design_solution",
                "error": str(e),
                "timestamp": state.updated_at.isoformat(),
            })
            raise

    async def _generate_code_node(self, state: WorkflowState) -> Dict[str, Any]:
        """生成代码节点"""
        try:
            state.current_step = "generate_code"

            # 获取设计方案
            solution_design = state.intermediate_results.get("solution_design", {})

            # 执行代码生成
            result = await self.agent_orchestrator.execute_agent(
                agent_type="development",
                input_data={
                    "task_description": solution_design.get("tasks", []),
                    "technical_requirements": state.input_data.get("technical_requirements", {}),
                    "code_context": state.input_data.get("code_context", {}),
                },
                context=state.intermediate_results
            )

            # 保存代码工件
            state.code_artifacts = result.get("generated_code", {})
            state.intermediate_results["generated_code"] = result
            state.step_history.append({
                "step": "generate_code",
                "timestamp": state.updated_at.isoformat(),
                "status": "completed",
                "result": result.get("status", "unknown"),
            })

            return {"workflow_state": state}

        except Exception as e:
            state.errors.append({
                "step": "generate_code",
                "error": str(e),
                "timestamp": state.updated_at.isoformat(),
            })
            raise

    def _check_code_quality(self, state: WorkflowState) -> str:
        """检查代码质量"""
        # 简单检查：如果有代码工件，进行评审；否则直接完成
        if state.code_artifacts:
            # 检查是否有明显的质量问题
            code_quality = state.intermediate_results.get("generated_code", {}).get("quality_score", 0)
            if code_quality < 70:  # 质量分数低于70需要评审
                return "needs_review"
            else:
                return "good_quality"
        else:
            return "error"

    async def _review_code_node(self, state: WorkflowState) -> Dict[str, Any]:
        """评审代码节点"""
        try:
            state.current_step = "review_code"

            # 获取生成的代码
            generated_code = state.intermediate_results.get("generated_code", {})

            # 执行代码评审
            result = await self.agent_orchestrator.execute_agent(
                agent_type="review",
                input_data={
                    "code": state.code_artifacts,
                    "code_metadata": generated_code,
                },
                context=state.intermediate_results
            )

            # 保存评审反馈
            state.review_feedback = result
            state.intermediate_results["code_review"] = result
            state.step_history.append({
                "step": "review_code",
                "timestamp": state.updated_at.isoformat(),
                "status": "completed",
                "result": result.get("status", "unknown"),
            })

            return {"workflow_state": state}

        except Exception as e:
            state.errors.append({
                "step": "review_code",
                "error": str(e),
                "timestamp": state.updated_at.isoformat(),
            })
            raise

    async def _finalize_node(self, state: WorkflowState) -> Dict[str, Any]:
        """完成节点"""
        try:
            state.current_step = "finalize"

            # 准备最终输出
            state.output_data = {
                "code_artifacts": state.code_artifacts,
                "review_feedback": state.review_feedback,
                "intermediate_results": state.intermediate_results,
                "step_history": state.step_history,
            }

            # 如果有评审反馈，包含改进建议
            if state.review_feedback:
                state.output_data["improvement_suggestions"] = state.review_feedback.get("suggestions", [])

            state.step_history.append({
                "step": "finalize",
                "timestamp": state.updated_at.isoformat(),
                "status": "completed",
            })

            return {"workflow_state": state}

        except Exception as e:
            state.errors.append({
                "step": "finalize",
                "error": str(e),
                "timestamp": state.updated_at.isoformat(),
            })
            raise

    async def _handle_error_node(self, state: WorkflowState) -> Dict[str, Any]:
        """错误处理节点"""
        state.current_step = "handle_error"

        # 记录错误
        error_summary = {
            "errors": state.errors,
            "last_step": state.current_step,
            "timestamp": state.updated_at.isoformat(),
        }

        state.output_data = {
            "status": "failed",
            "error_summary": error_summary,
            "step_history": state.step_history,
        }

        return {"workflow_state": state}


class ReviewWorkflow(BaseWorkflow):
    """评审工作流"""

    def __init__(self, agent_orchestrator: AgentOrchestrator):
        super().__init__(agent_orchestrator)
        self._build_graph()

    def _build_graph(self):
        """构建评审工作流图"""

        # 定义节点
        self.graph.add_node("start", self._start_node)
        self.graph.add_node("analyze_code", self._analyze_code_node)
        self.graph.add_node("check_quality", self._check_quality_node)
        self.graph.add_node("check_security", self._check_security_node)
        self.graph.add_node("check_performance", self._check_performance_node)
        self.graph.add_node("generate_feedback", self._generate_feedback_node)
        self.graph.add_node("finalize", self._finalize_node)
        self.graph.add_node("handle_error", self._handle_error_node)

        # 定义边
        self.graph.set_entry_point("start")
        self.graph.add_edge("start", "analyze_code")
        self.graph.add_edge("analyze_code", "check_quality")
        self.graph.add_conditional_edges(
            "check_quality",
            self._check_quality_result,
            {
                "needs_security_check": "check_security",
                "needs_performance_check": "check_performance",
                "good_quality": "generate_feedback",
                "poor_quality": "handle_error",
            }
        )
        self.graph.add_edge("check_security", "check_performance")
        self.graph.add_edge("check_performance", "generate_feedback")
        self.graph.add_edge("generate_feedback", "finalize")
        self.graph.add_edge("handle_error", END)
        self.graph.add_edge("finalize", END)

    async def _start_node(self, state: WorkflowState) -> Dict[str, Any]:
        """开始节点"""
        state.current_step = "start"
        state.step_history.append({
            "step": "start",
            "timestamp": state.updated_at.isoformat(),
            "status": "started",
        })
        return {"workflow_state": state}

    async def _analyze_code_node(self, state: WorkflowState) -> Dict[str, Any]:
        """分析代码节点"""
        try:
            state.current_step = "analyze_code"

            # 获取输入代码
            code_data = state.input_data.get("code", {})

            # 分析代码结构和质量
            # 这里可以调用代码分析工具或智能体
            analysis_result = {
                "language": code_data.get("language", "unknown"),
                "size": len(str(code_data.get("content", ""))),
                "complexity": "medium",  # 简化示例
                "structure": "valid",  # 简化示例
            }

            state.intermediate_results["code_analysis"] = analysis_result
            state.step_history.append({
                "step": "analyze_code",
                "timestamp": state.updated_at.isoformat(),
                "status": "completed",
            })

            return {"workflow_state": state}

        except Exception as e:
            state.errors.append({
                "step": "analyze_code",
                "error": str(e),
                "timestamp": state.updated_at.isoformat(),
            })
            raise

    async def _check_quality_node(self, state: WorkflowState) -> Dict[str, Any]:
        """检查代码质量节点"""
        try:
            state.current_step = "check_quality"

            # 获取代码分析结果
            code_analysis = state.intermediate_results.get("code_analysis", {})

            # 执行质量检查
            result = await self.agent_orchestrator.execute_agent(
                agent_type="review",
                input_data={
                    "check_type": "quality",
                    "code_analysis": code_analysis,
                    "code": state.input_data.get("code", {}),
                },
                context=state.intermediate_results
            )

            state.intermediate_results["quality_check"] = result
            state.step_history.append({
                "step": "check_quality",
                "timestamp": state.updated_at.isoformat(),
                "status": "completed",
            })

            return {"workflow_state": state}

        except Exception as e:
            state.errors.append({
                "step": "check_quality",
                "error": str(e),
                "timestamp": state.updated_at.isoformat(),
            })
            raise

    def _check_quality_result(self, state: WorkflowState) -> str:
        """检查质量结果"""
        quality_check = state.intermediate_results.get("quality_check", {})

        # 简化逻辑：根据质量分数决定下一步
        quality_score = quality_check.get("score", 0)
        needs_security = quality_check.get("needs_security_check", False)
        needs_performance = quality_check.get("needs_performance_check", False)

        if quality_score < 50:
            return "poor_quality"
        elif needs_security:
            return "needs_security_check"
        elif needs_performance:
            return "needs_performance_check"
        else:
            return "good_quality"

    async def _check_security_node(self, state: WorkflowState) -> Dict[str, Any]:
        """检查安全性节点"""
        try:
            state.current_step = "check_security"

            # 执行安全检查
            result = await self.agent_orchestrator.execute_agent(
                agent_type="review",
                input_data={
                    "check_type": "security",
                    "code": state.input_data.get("code", {}),
                    "code_analysis": state.intermediate_results.get("code_analysis", {}),
                },
                context=state.intermediate_results
            )

            state.intermediate_results["security_check"] = result
            state.step_history.append({
                "step": "check_security",
                "timestamp": state.updated_at.isoformat(),
                "status": "completed",
            })

            return {"workflow_state": state}

        except Exception as e:
            state.errors.append({
                "step": "check_security",
                "error": str(e),
                "timestamp": state.updated_at.isoformat(),
            })
            raise

    async def _check_performance_node(self, state: WorkflowState) -> Dict[str, Any]:
        """检查性能节点"""
        try:
            state.current_step = "check_performance"

            # 执行性能检查
            result = await self.agent_orchestrator.execute_agent(
                agent_type="review",
                input_data={
                    "check_type": "performance",
                    "code": state.input_data.get("code", {}),
                    "code_analysis": state.intermediate_results.get("code_analysis", {}),
                },
                context=state.intermediate_results
            )

            state.intermediate_results["performance_check"] = result
            state.step_history.append({
                "step": "check_performance",
                "timestamp": state.updated_at.isoformat(),
                "status": "completed",
            })

            return {"workflow_state": state}

        except Exception as e:
            state.errors.append({
                "step": "check_performance",
                "error": str(e),
                "timestamp": state.updated_at.isoformat(),
            })
            raise

    async def _generate_feedback_node(self, state: WorkflowState) -> Dict[str, Any]:
        """生成反馈节点"""
        try:
            state.current_step = "generate_feedback"

            # 汇总所有检查结果
            quality_check = state.intermediate_results.get("quality_check", {})
            security_check = state.intermediate_results.get("security_check", {})
            performance_check = state.intermediate_results.get("performance_check", {})

            # 生成综合反馈
            feedback = {
                "quality": quality_check.get("feedback", []),
                "security": security_check.get("issues", []),
                "performance": performance_check.get("suggestions", []),
                "overall_score": (
                    quality_check.get("score", 0) * 0.4 +
                    (100 - len(security_check.get("issues", [])) * 10) * 0.3 +
                    performance_check.get("score", 0) * 0.3
                ),
                "recommendations": [
                    *quality_check.get("recommendations", []),
                    *security_check.get("recommendations", []),
                    *performance_check.get("recommendations", []),
                ],
            }

            state.review_feedback = feedback
            state.step_history.append({
                "step": "generate_feedback",
                "timestamp": state.updated_at.isoformat(),
                "status": "completed",
            })

            return {"workflow_state": state}

        except Exception as e:
            state.errors.append({
                "step": "generate_feedback",
                "error": str(e),
                "timestamp": state.updated_at.isoformat(),
            })
            raise

    async def _finalize_node(self, state: WorkflowState) -> Dict[str, Any]:
        """完成节点"""
        try:
            state.current_step = "finalize"

            state.output_data = {
                "review_feedback": state.review_feedback,
                "intermediate_results": state.intermediate_results,
                "step_history": state.step_history,
            }

            state.step_history.append({
                "step": "finalize",
                "timestamp": state.updated_at.isoformat(),
                "status": "completed",
            })

            return {"workflow_state": state}

        except Exception as e:
            state.errors.append({
                "step": "finalize",
                "error": str(e),
                "timestamp": state.updated_at.isoformat(),
            })
            raise

    async def _handle_error_node(self, state: WorkflowState) -> Dict[str, Any]:
        """错误处理节点"""
        state.current_step = "handle_error"

        state.output_data = {
            "status": "failed",
            "error": "代码质量过低，无法进行后续评审",
            "quality_check": state.intermediate_results.get("quality_check", {}),
            "step_history": state.step_history,
        }

        return {"workflow_state": state}


class TestWorkflow(BaseWorkflow):
    """测试工作流"""

    def __init__(self, agent_orchestrator: AgentOrchestrator):
        super().__init__(agent_orchestrator)
        self._build_graph()

    def _build_graph(self):
        """构建测试工作流图"""

        # 定义节点
        self.graph.add_node("start", self._start_node)
        self.graph.add_node("analyze_code", self._analyze_code_node)
        self.graph.add_node("generate_tests", self._generate_tests_node)
        self.graph.add_node("execute_tests", self._execute_tests_node)
        self.graph.add_node("analyze_results", self._analyze_results_node)
        self.graph.add_node("finalize", self._finalize_node)
        self.graph.add_node("handle_error", self._handle_error_node)

        # 定义边
        self.graph.set_entry_point("start")
        self.graph.add_edge("start", "analyze_code")
        self.graph.add_edge("analyze_code", "generate_tests")
        self.graph.add_conditional_edges(
            "generate_tests",
            self._check_tests_generated,
            {
                "tests_generated": "execute_tests",
                "no_tests": "handle_error",
            }
        )
        self.graph.add_edge("execute_tests", "analyze_results")
        self.graph.add_conditional_edges(
            "analyze_results",
            self._check_test_results,
            {
                "tests_passed": "finalize",
                "tests_failed": "handle_error",
            }
        )
        self.graph.add_edge("handle_error", END)
        self.graph.add_edge("finalize", END)

    async def _start_node(self, state: WorkflowState) -> Dict[str, Any]:
        """开始节点"""
        state.current_step = "start"
        state.step_history.append({
            "step": "start",
            "timestamp": state.updated_at.isoformat(),
            "status": "started",
        })
        return {"workflow_state": state}

    async def _analyze_code_node(self, state: WorkflowState) -> Dict[str, Any]:
        """分析代码节点"""
        try:
            state.current_step = "analyze_code"

            # 分析代码结构和测试需求
            code_data = state.input_data.get("code", {})
            function_description = state.input_data.get("function_description", "")

            analysis_result = {
                "code_size": len(str(code_data.get("content", ""))),
                "language": code_data.get("language", "unknown"),
                "function_description": function_description,
                "test_requirements": [
                    "unit_tests",
                    "boundary_tests",
                    "exception_tests",
                ],
            }

            state.intermediate_results["code_analysis"] = analysis_result
            state.step_history.append({
                "step": "analyze_code",
                "timestamp": state.updated_at.isoformat(),
                "status": "completed",
            })

            return {"workflow_state": state}

        except Exception as e:
            state.errors.append({
                "step": "analyze_code",
                "error": str(e),
                "timestamp": state.updated_at.isoformat(),
            })
            raise

    async def _generate_tests_node(self, state: WorkflowState) -> Dict[str, Any]:
        """生成测试节点"""
        try:
            state.current_step = "generate_tests"

            # 获取代码分析结果
            code_analysis = state.intermediate_results.get("code_analysis", {})

            # 生成测试用例
            result = await self.agent_orchestrator.execute_agent(
                agent_type="test",
                input_data={
                    "code": state.input_data.get("code", {}),
                    "function_description": code_analysis.get("function_description", ""),
                    "test_requirements": code_analysis.get("test_requirements", []),
                },
                context=state.intermediate_results
            )

            state.intermediate_results["generated_tests"] = result
            state.test_results["generated_tests"] = result.get("test_cases", [])
            state.step_history.append({
                "step": "generate_tests",
                "timestamp": state.updated_at.isoformat(),
                "status": "completed",
            })

            return {"workflow_state": state}

        except Exception as e:
            state.errors.append({
                "step": "generate_tests",
                "error": str(e),
                "timestamp": state.updated_at.isoformat(),
            })
            raise

    def _check_tests_generated(self, state: WorkflowState) -> str:
        """检查是否生成了测试"""
        generated_tests = state.intermediate_results.get("generated_tests", {})
        test_cases = generated_tests.get("test_cases", [])

        if test_cases and len(test_cases) > 0:
            return "tests_generated"
        else:
            return "no_tests"

    async def _execute_tests_node(self, state: WorkflowState) -> Dict[str, Any]:
        """执行测试节点"""
        try:
            state.current_step = "execute_tests"

            # 获取生成的测试
            generated_tests = state.intermediate_results.get("generated_tests", {})

            # 执行测试
            # 这里可以调用测试执行框架
            execution_result = {
                "test_cases_executed": len(generated_tests.get("test_cases", [])),
                "passed": len(generated_tests.get("test_cases", [])) * 0.8,  # 模拟80%通过率
                "failed": len(generated_tests.get("test_cases", [])) * 0.2,  # 模拟20%失败率
                "skipped": 0,
                "execution_time": 2.5,  # 模拟执行时间
            }

            state.intermediate_results["test_execution"] = execution_result
            state.test_results["execution"] = execution_result
            state.step_history.append({
                "step": "execute_tests",
                "timestamp": state.updated_at.isoformat(),
                "status": "completed",
            })

            return {"workflow_state": state}

        except Exception as e:
            state.errors.append({
                "step": "execute_tests",
                "error": str(e),
                "timestamp": state.updated_at.isoformat(),
            })
            raise

    async def _analyze_results_node(self, state: WorkflowState) -> Dict[str, Any]:
        """分析结果节点"""
        try:
            state.current_step = "analyze_results"

            # 获取测试执行结果
            test_execution = state.intermediate_results.get("test_execution", {})

            # 分析测试结果
            analysis_result = {
                "coverage": (test_execution.get("passed", 0) / test_execution.get("test_cases_executed", 1)) * 100,
                "pass_rate": (test_execution.get("passed", 0) / test_execution.get("test_cases_executed", 1)) * 100,
                "issues_found": test_execution.get("failed", 0),
                "recommendations": [
                    "增加边界测试" if test_execution.get("failed", 0) > 0 else "",
                    "提高测试覆盖率" if test_execution.get("passed", 0) / test_execution.get("test_cases_executed", 1) < 0.9 else "",
                ],
            }

            state.intermediate_results["results_analysis"] = analysis_result
            state.step_history.append({
                "step": "analyze_results",
                "timestamp": state.updated_at.isoformat(),
                "status": "completed",
            })

            return {"workflow_state": state}

        except Exception as e:
            state.errors.append({
                "step": "analyze_results",
                "error": str(e),
                "timestamp": state.updated_at.isoformat(),
            })
            raise

    def _check_test_results(self, state: WorkflowState) -> str:
        """检查测试结果"""
        results_analysis = state.intermediate_results.get("results_analysis", {})
        pass_rate = results_analysis.get("pass_rate", 0)

        if pass_rate >= 80:  # 通过率80%以上认为测试通过
            return "tests_passed"
        else:
            return "tests_failed"

    async def _finalize_node(self, state: WorkflowState) -> Dict[str, Any]:
        """完成节点"""
        try:
            state.current_step = "finalize"

            state.output_data = {
                "test_results": state.test_results,
                "results_analysis": state.intermediate_results.get("results_analysis", {}),
                "step_history": state.step_history,
            }

            state.step_history.append({
                "step": "finalize",
                "timestamp": state.updated_at.isoformat(),
                "status": "completed",
            })

            return {"workflow_state": state}

        except Exception as e:
            state.errors.append({
                "step": "finalize",
                "error": str(e),
                "timestamp": state.updated_at.isoformat(),
            })
            raise

    async def _handle_error_node(self, state: WorkflowState) -> Dict[str, Any]:
        """错误处理节点"""
        state.current_step = "handle_error"

        error_type = "no_tests_generated" if "no_tests" in state.current_step else "tests_failed"

        state.output_data = {
            "status": "failed",
            "error_type": error_type,
            "test_results": state.test_results,
            "step_history": state.step_history,
        }

        return {"workflow_state": state}


class FullDevelopmentWorkflow(BaseWorkflow):
    """完整开发工作流（需求分析 → 任务规划 → 开发 → 评审 → 测试）"""

    def __init__(self, agent_orchestrator: AgentOrchestrator):
        super().__init__(agent_orchestrator)
        self._build_graph()

    def _build_graph(self):
        """构建完整开发工作流图"""

        # 定义节点
        self.graph.add_node("start", self._start_node)
        self.graph.add_node("requirement_analysis", self._requirement_analysis_node)
        self.graph.add_node("task_planning", self._task_planning_node)
        self.graph.add_node("development", self._development_node)
        self.graph.add_node("code_review", self._code_review_node)
        self.graph.add_node("testing", self._testing_node)
        self.graph.add_node("deployment_prep", self._deployment_prep_node)
        self.graph.add_node("finalize", self._finalize_node)
        self.graph.add_node("handle_error", self._handle_error_node)

        # 定义边
        self.graph.set_entry_point("start")
        self.graph.add_edge("start", "requirement_analysis")
        self.graph.add_conditional_edges(
            "requirement_analysis",
            self._check_requirement_analysis,
            {
                "valid_requirements": "task_planning",
                "invalid_requirements": "handle_error",
            }
        )
        self.graph.add_edge("task_planning", "development")
        self.graph.add_conditional_edges(
            "development",
            self._check_development_result,
            {
                "code_generated": "code_review",
                "development_failed": "handle_error",
            }
        )
        self.graph.add_conditional_edges(
            "code_review",
            self._check_review_result,
            {
                "review_passed": "testing",
                "needs_rework": "development",
                "review_failed": "handle_error",
            }
        )
        self.graph.add_conditional_edges(
            "testing",
            self._check_testing_result,
            {
                "tests_passed": "deployment_prep",
                "needs_fixes": "development",
                "tests_failed": "handle_error",
            }
        )
        self.graph.add_edge("deployment_prep", "finalize")
        self.graph.add_edge("handle_error", END)
        self.graph.add_edge("finalize", END)

    async def _start_node(self, state: WorkflowState) -> Dict[str, Any]:
        """开始节点"""
        state.current_step = "start"
        state.step_history.append({
            "step": "start",
            "timestamp": state.updated_at.isoformat(),
            "status": "started",
        })
        return {"workflow_state": state}

    async def _requirement_analysis_node(self, state: WorkflowState) -> Dict[str, Any]:
        """需求分析节点"""
        try:
            state.current_step = "requirement_analysis"

            # 执行需求分析
            result = await self.agent_orchestrator.execute_agent(
                agent_type="requirement",
                input_data=state.input_data.get("requirement_data", {}),
                context=state.intermediate_results
            )

            state.intermediate_results["requirement_analysis"] = result
            state.step_history.append({
                "step": "requirement_analysis",
                "timestamp": state.updated_at.isoformat(),
                "status": "completed",
            })

            return {"workflow_state": state}

        except Exception as e:
            state.errors.append({
                "step": "requirement_analysis",
                "error": str(e),
                "timestamp": state.updated_at.isoformat(),
            })
            raise

    def _check_requirement_analysis(self, state: WorkflowState) -> str:
        """检查需求分析结果"""
        requirement_analysis = state.intermediate_results.get("requirement_analysis", {})

        # 检查需求是否有效
        if requirement_analysis.get("status") == "success":
            requirements = requirement_analysis.get("requirements", [])
            if requirements and len(requirements) > 0:
                return "valid_requirements"

        return "invalid_requirements"

    async def _task_planning_node(self, state: WorkflowState) -> Dict[str, Any]:
        """任务规划节点"""
        try:
            state.current_step = "task_planning"

            # 获取需求分析结果
            requirement_analysis = state.intermediate_results.get("requirement_analysis", {})

            # 执行任务规划
            result = await self.agent_orchestrator.execute_agent(
                agent_type="task_planner",
                input_data={
                    "requirement_spec": requirement_analysis,
                    "project_context": state.input_data.get("project_context", {}),
                },
                context=state.intermediate_results
            )

            state.intermediate_results["task_plan"] = result
            state.step_history.append({
                "step": "task_planning",
                "timestamp": state.updated_at.isoformat(),
                "status": "completed",
            })

            return {"workflow_state": state}

        except Exception as e:
            state.errors.append({
                "step": "task_planning",
                "error": str(e),
                "timestamp": state.updated_at.isoformat(),
            })
            raise

    async def _development_node(self, state: WorkflowState) -> Dict[str, Any]:
        """开发节点"""
        try:
            state.current_step = "development"

            # 获取任务计划
            task_plan = state.intermediate_results.get("task_plan", {})

            # 执行开发
            result = await self.agent_orchestrator.execute_agent(
                agent_type="development",
                input_data={
                    "task_description": task_plan.get("tasks", []),
                    "technical_requirements": state.input_data.get("technical_requirements", {}),
                    "code_context": state.input_data.get("code_context", {}),
                },
                context=state.intermediate_results
            )

            state.intermediate_results["development_result"] = result
            state.code_artifacts = result.get("generated_code", {})
            state.step_history.append({
                "step": "development",
                "timestamp": state.updated_at.isoformat(),
                "status": "completed",
            })

            return {"workflow_state": state}

        except Exception as e:
            state.errors.append({
                "step": "development",
                "error": str(e),
                "timestamp": state.updated_at.isoformat(),
            })
            raise

    def _check_development_result(self, state: WorkflowState) -> str:
        """检查开发结果"""
        development_result = state.intermediate_results.get("development_result", {})

        if development_result.get("status") == "success" and state.code_artifacts:
            return "code_generated"
        else:
            return "development_failed"

    async def _code_review_node(self, state: WorkflowState) -> Dict[str, Any]:
        """代码评审节点"""
        try:
            state.current_step = "code_review"

            # 执行代码评审
            result = await self.agent_orchestrator.execute_agent(
                agent_type="review",
                input_data={
                    "code": state.code_artifacts,
                    "code_metadata": state.intermediate_results.get("development_result", {}),
                },
                context=state.intermediate_results
            )

            state.intermediate_results["code_review"] = result
            state.review_feedback = result
            state.step_history.append({
                "step": "code_review",
                "timestamp": state.updated_at.isoformat(),
                "status": "completed",
            })

            return {"workflow_state": state}

        except Exception as e:
            state.errors.append({
                "step": "code_review",
                "error": str(e),
                "timestamp": state.updated_at.isoformat(),
            })
            raise

    def _check_review_result(self, state: WorkflowState) -> str:
        """检查评审结果"""
        code_review = state.intermediate_results.get("code_review", {})
        review_score = code_review.get("score", 0)

        if review_score >= 80:
            return "review_passed"
        elif review_score >= 60:
            return "needs_rework"
        else:
            return "review_failed"

    async def _testing_node(self, state: WorkflowState) -> Dict[str, Any]:
        """测试节点"""
        try:
            state.current_step = "testing"

            # 执行测试
            result = await self.agent_orchestrator.execute_agent(
                agent_type="test",
                input_data={
                    "code": state.code_artifacts,
                    "function_description": state.input_data.get("function_description", ""),
                },
                context=state.intermediate_results
            )

            state.intermediate_results["testing_result"] = result
            state.test_results = result.get("test_results", {})
            state.step_history.append({
                "step": "testing",
                "timestamp": state.updated_at.isoformat(),
                "status": "completed",
            })

            return {"workflow_state": state}

        except Exception as e:
            state.errors.append({
                "step": "testing",
                "error": str(e),
                "timestamp": state.updated_at.isoformat(),
            })
            raise

    def _check_testing_result(self, state: WorkflowState) -> str:
        """检查测试结果"""
        testing_result = state.intermediate_results.get("testing_result", {})
        test_pass_rate = testing_result.get("pass_rate", 0)

        if test_pass_rate >= 90:
            return "tests_passed"
        elif test_pass_rate >= 70:
            return "needs_fixes"
        else:
            return "tests_failed"

    async def _deployment_prep_node(self, state: WorkflowState) -> Dict[str, Any]:
        """部署准备节点"""
        try:
            state.current_step = "deployment_prep"

            # 准备部署包
            deployment_package = {
                "code_artifacts": state.code_artifacts,
                "review_feedback": state.review_feedback,
                "test_results": state.test_results,
                "documentation": state.intermediate_results.get("development_result", {}).get("documentation", {}),
            }

            state.intermediate_results["deployment_package"] = deployment_package
            state.step_history.append({
                "step": "deployment_prep",
                "timestamp": state.updated_at.isoformat(),
                "status": "completed",
            })

            return {"workflow_state": state}

        except Exception as e:
            state.errors.append({
                "step": "deployment_prep",
                "error": str(e),
                "timestamp": state.updated_at.isoformat(),
            })
            raise

    async def _finalize_node(self, state: WorkflowState) -> Dict[str, Any]:
        """完成节点"""
        try:
            state.current_step = "finalize"

            state.output_data = {
                "status": "success",
                "deliverables": {
                    "code": state.code_artifacts,
                    "documentation": state.intermediate_results.get("development_result", {}).get("documentation", {}),
                    "test_results": state.test_results,
                    "review_feedback": state.review_feedback,
                },
                "quality_metrics": {
                    "code_quality": state.review_feedback.get("score", 0),
                    "test_coverage": state.test_results.get("coverage", 0),
                    "requirements_fulfilled": len(state.intermediate_results.get("requirement_analysis", {}).get("requirements", [])),
                },
                "step_history": state.step_history,
                "intermediate_results": state.intermediate_results,
            }

            state.step_history.append({
                "step": "finalize",
                "timestamp": state.updated_at.isoformat(),
                "status": "completed",
            })

            return {"workflow_state": state}

        except Exception as e:
            state.errors.append({
                "step": "finalize",
                "error": str(e),
                "timestamp": state.updated_at.isoformat(),
            })
            raise

    async def _handle_error_node(self, state: WorkflowState) -> Dict[str, Any]:
        """错误处理节点"""
        state.current_step = "handle_error"

        # 确定错误类型
        error_step = state.current_step
        error_data = {
            "failed_step": error_step,
            "errors": state.errors,
            "intermediate_results": state.intermediate_results,
        }

        state.output_data = {
            "status": "failed",
            "error_data": error_data,
            "step_history": state.step_history,
        }

        return {"workflow_state": state}


def get_workflow_definition(workflow_type: str) -> Optional[Type[BaseWorkflow]]:
    """
    获取工作流定义类

    Args:
        workflow_type: 工作流类型

    Returns:
        工作流定义类
    """
    workflow_classes = {
        "development": DevelopmentWorkflow,
        "review": ReviewWorkflow,
        "test": TestWorkflow,
        "full_development": FullDevelopmentWorkflow,
    }

    return workflow_classes.get(workflow_type)