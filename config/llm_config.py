"""LLM配置

管理LLM客户端和提示模板配置。
"""

from typing import Dict, Any, Optional
from enum import Enum
from pydantic import BaseModel


class LLMProvider(str, Enum):
    """LLM提供商枚举"""
    CLAUDE = "claude"
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    LOCAL = "local"


class LLMConfig(BaseModel):
    """LLM基础配置"""
    provider: LLMProvider = LLMProvider.CLAUDE
    model: str = "claude-3-5-sonnet-20241022"
    temperature: float = 0.7
    max_tokens: int = 4000
    timeout: int = 120
    max_retries: int = 3


class EmbeddingConfig(BaseModel):
    """嵌入模型配置"""
    provider: LLMProvider = LLMProvider.OPENAI
    model: str = "text-embedding-3-small"
    dimensions: Optional[int] = None
    timeout: int = 60
    max_retries: int = 3


class PromptTemplate(BaseModel):
    """提示模板配置"""
    template: str
    input_variables: list
    output_format: Optional[str] = None


# 提示模板配置
PROMPT_TEMPLATES: Dict[str, PromptTemplate] = {
    "requirement_analysis": PromptTemplate(
        template="""
        作为需求分析专家，请分析以下文档并提取结构化需求：

        文档内容：
        {document_content}

        请提取以下信息：
        1. 项目目标和范围
        2. 主要功能需求
        3. 非功能需求（性能、安全、可用性等）
        4. 技术约束和要求
        5. 假设和依赖

        请以JSON格式返回。
        """,
        input_variables=["document_content"],
        output_format="json"
    ),
    "task_decomposition": PromptTemplate(
        template="""
        作为项目规划师，请将以下需求分解为开发任务：

        需求规格：
        {requirement_spec}

        考虑因素：
        1. 任务依赖关系
        2. 优先级（高/中/低）
        3. 预估工作量（小时）
        4. 所需技能和技术

        请生成任务列表，每个任务包含：
        - 任务ID
        - 任务描述
        - 优先级
        - 预估工时
        - 依赖任务（如有）
        - 所需技能

        以JSON数组格式返回。
        """,
        input_variables=["requirement_spec"],
        output_format="json"
    ),
    "code_generation": PromptTemplate(
        template="""
        作为软件工程师，请为以下任务生成代码：

        任务描述：
        {task_description}

        技术要求：
        {technical_requirements}

        代码规范：
        1. 遵循{language}最佳实践
        2. 添加适当的注释
        3. 包含错误处理
        4. 考虑性能优化
        5. 确保安全性

        请生成完整的代码实现。
        """,
        input_variables=["task_description", "technical_requirements", "language"],
        output_format="code"
    ),
    "code_review": PromptTemplate(
        template="""
        作为代码评审专家，请评审以下代码：

        代码：
        {code}

        功能描述：
        {function_description}

        请从以下方面评审：
        1. 代码质量和可读性
        2. 安全性和潜在漏洞
        3. 性能和优化机会
        4. 是否符合最佳实践
        5. 测试覆盖情况

        提供具体的改进建议。
        """,
        input_variables=["code", "function_description"],
        output_format="markdown"
    ),
    "test_generation": PromptTemplate(
        template="""
        作为测试工程师，请为以下代码生成测试：

        代码：
        {code}

        功能描述：
        {function_description}

        使用{test_framework}框架生成全面的测试用例，包括：
        1. 正常路径测试
        2. 边界条件测试
        3. 异常处理测试
        4. 性能测试（如适用）

        请生成完整的测试代码。
        """,
        input_variables=["code", "function_description", "test_framework"],
        output_format="code"
    ),
}

# LLM客户端配置
LLM_CONFIGS: Dict[str, LLMConfig] = {
    "default": LLMConfig(),
    "claude_haiku": LLMConfig(
        provider=LLMProvider.CLAUDE,
        model="claude-3-haiku-20240307",
        temperature=0.7,
        max_tokens=4000
    ),
    "claude_sonnet": LLMConfig(
        provider=LLMProvider.CLAUDE,
        model="claude-3-5-sonnet-20241022",
        temperature=0.7,
        max_tokens=4000
    ),
    "gpt4_turbo": LLMConfig(
        provider=LLMProvider.OPENAI,
        model="gpt-4-turbo-preview",
        temperature=0.7,
        max_tokens=4000
    ),
    "gpt3_turbo": LLMConfig(
        provider=LLMProvider.OPENAI,
        model="gpt-3.5-turbo",
        temperature=0.7,
        max_tokens=4000
    ),
}

# 嵌入模型配置
EMBEDDING_CONFIGS: Dict[str, EmbeddingConfig] = {
    "openai_small": EmbeddingConfig(
        provider=LLMProvider.OPENAI,
        model="text-embedding-3-small",
        dimensions=1536
    ),
    "openai_large": EmbeddingConfig(
        provider=LLMProvider.OPENAI,
        model="text-embedding-3-large",
        dimensions=3072
    ),
    "bge_m3": EmbeddingConfig(
        provider=LLMProvider.LOCAL,
        model="BAAI/bge-m3",
        dimensions=1024
    ),
}