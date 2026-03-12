"""智能体配置

定义各个智能体的配置参数。
"""

from typing import Dict, Any
from pydantic import BaseModel


class AgentConfig(BaseModel):
    """智能体基础配置"""
    enabled: bool = True
    max_retries: int = 3
    timeout: int = 300
    temperature: float = 0.7
    max_tokens: int = 4000


class RequirementAgentConfig(AgentConfig):
    """需求智能体配置"""
    clarification_prompt_template: str = """
    你是一个需求分析专家。请分析以下需求文档：

    {document_content}

    请回答以下问题：
    1. 这个需求的核心目标是什么？
    2. 主要功能点有哪些？
    3. 有哪些技术约束或要求？
    4. 有哪些假设或前提条件？
    5. 建议的技术栈是什么？

    请以JSON格式返回结构化需求规格。
    """
    output_schema: Dict[str, Any] = {
        "title": "需求标题",
        "description": "需求描述",
        "core_objectives": ["目标1", "目标2"],
        "features": ["功能1", "功能2"],
        "technical_constraints": ["约束1", "约束2"],
        "assumptions": ["假设1", "假设2"],
        "suggested_tech_stack": ["技术1", "技术2"]
    }


class TaskPlannerConfig(AgentConfig):
    """任务规划智能体配置"""
    decomposition_prompt_template: str = """
    你是一个项目规划专家。请根据以下需求规格分解开发任务：

    {requirement_spec}

    请将需求分解为具体的开发任务，考虑以下因素：
    1. 任务之间的依赖关系
    2. 任务优先级（高/中/低）
    3. 预估工作量（以小时为单位）
    4. 所需技能

    请以JSON格式返回任务分解结果。
    """
    max_tasks_per_requirement: int = 20
    min_task_hours: int = 1
    max_task_hours: int = 40


class DevelopmentAgentConfig(AgentConfig):
    """开发智能体配置"""
    code_generation_prompt_template: str = """
    你是一个资深软件工程师。请根据以下任务描述生成代码：

    {task_description}

    技术要求：
    {technical_requirements}

    现有代码上下文：
    {code_context}

    请生成高质量、可维护的代码，包含必要的注释和文档。
    """
    preferred_languages: list = ["python", "javascript", "typescript", "java", "go"]
    include_tests: bool = True
    include_documentation: bool = True


class ReviewAgentConfig(AgentConfig):
    """评审智能体配置"""
    review_prompt_template: str = """
    你是一个代码评审专家。请评审以下代码：

    {code}

    请从以下角度进行评审：
    1. 代码质量（可读性、可维护性）
    2. 安全性（潜在的安全漏洞）
    3. 性能（潜在的优化点）
    4. 是否符合最佳实践
    5. 测试覆盖情况

    请提供具体的改进建议。
    """
    check_security: bool = True
    check_performance: bool = True
    check_best_practices: bool = True


class TestAgentConfig(AgentConfig):
    """测试智能体配置"""
    test_generation_prompt_template: str = """
    你是一个测试专家。请为以下代码生成测试用例：

    {code}

    功能描述：
    {function_description}

    请生成全面的测试用例，包括：
    1. 单元测试
    2. 边界条件测试
    3. 异常处理测试
    4. 集成测试场景
    """
    test_framework: str = "pytest"  # 或 "unittest", "jest"等
    min_test_coverage: float = 0.8


# 智能体配置集合
AGENTS_CONFIG = {
    "requirement": RequirementAgentConfig(),
    "task_planner": TaskPlannerConfig(),
    "development": DevelopmentAgentConfig(),
    "review": ReviewAgentConfig(),
    "test": TestAgentConfig(),
}