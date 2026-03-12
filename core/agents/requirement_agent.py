"""需求智能体

分析需求文档，生成结构化需求规格。
"""

from typing import Dict, Any, List, Optional
import json
import re
import loguru

from .base_agent import BaseAgent
from config.agents_config import RequirementAgentConfig
from utils.llm_client import LLMClient

logger = loguru.logger

class RequirementAgent(BaseAgent):
    """需求智能体"""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """初始化需求智能体"""
        config = RequirementAgentConfig()
        super().__init__(
            name="requirement_agent",
            config=config,
            llm_client=llm_client
        )

        self.prompt_template = config.clarification_prompt_template
        self.output_schema = config.output_schema

        logger.info("需求智能体初始化完成")

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理需求分析

        Args:
            input_data: 输入数据，包含需求文档和分析上下文

        Returns:
            结构化需求规格
        """
        try:
            # 验证输入
            if not await self.validate_input(input_data):
                raise ValueError("输入数据验证失败")

            # 准备提示
            prompt = self._prepare_prompt(input_data)

            # 调用LLM进行分析
            analysis_result = await self._analyze_with_llm(prompt)

            # 验证输出
            if not await self.validate_output(analysis_result):
                raise ValueError("分析结果验证失败")

            # 添加元数据
            analysis_result["metadata"] = {
                "agent": self.name,
                "analysis_timestamp": self._get_current_timestamp(),
                "input_summary": self._summarize_input(input_data),
            }

            logger.info(f"需求分析完成，生成 {len(analysis_result)} 个字段")
            return analysis_result

        except Exception as e:
            logger.error(f"需求分析失败: {str(e)}")
            raise

    async def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """验证输入数据"""
        if not await super().validate_input(input_data):
            return False

        # 检查必要字段
        required_fields = ["title"]
        for field in required_fields:
            if field not in input_data:
                logger.warning(f"输入数据缺少必要字段: {field}")
                return False

        # 检查内容长度
        title = input_data.get("title", "")
        description = input_data.get("description", "")

        if len(title) < 3:
            logger.warning(f"需求标题太短: {title}")
            return False

        if len(description) > 10000:  # 描述过长
            logger.warning("需求描述过长")
            return False

        return True

    async def validate_output(self, output_data: Dict[str, Any]) -> bool:
        """验证输出数据"""
        if not await super().validate_output(output_data):
            return False

        # 检查必要字段
        required_fields = ["title", "description", "core_objectives", "features"]
        for field in required_fields:
            if field not in output_data:
                logger.warning(f"输出数据缺少必要字段: {field}")
                return False

        # 验证字段类型
        if not isinstance(output_data.get("core_objectives"), list):
            logger.warning("core_objectives 必须是列表")
            return False

        if not isinstance(output_data.get("features"), list):
            logger.warning("features 必须是列表")
            return False

        # 验证列表内容
        if len(output_data["core_objectives"]) == 0:
            logger.warning("core_objectives 不能为空")
            return False

        if len(output_data["features"]) == 0:
            logger.warning("features 不能为空")
            return False

        return True

    def _prepare_prompt(self, input_data: Dict[str, Any]) -> str:
        """准备提示"""
        # 提取文档内容
        document_content = self._extract_document_content(input_data)

        # 构建上下文
        context = {
            "title": input_data.get("title", ""),
            "description": input_data.get("description", ""),
            "document_content": document_content,
            "related_knowledge": input_data.get("related_knowledge", []),
            "metadata": input_data.get("metadata", {}),
        }

        # 格式化提示
        prompt = self.prompt_template.format(**context)

        # 添加输出格式要求
        prompt += f"\n\n请严格按照以下JSON格式返回结果:\n{json.dumps(self.output_schema, indent=2, ensure_ascii=False)}"

        return prompt

    def _extract_document_content(self, input_data: Dict[str, Any]) -> str:
        """提取文档内容"""
        content_parts = []

        # 标题和描述
        if title := input_data.get("title"):
            content_parts.append(f"标题: {title}")

        if description := input_data.get("description"):
            content_parts.append(f"描述: {description}")

        # 文档路径内容（如果有）
        if document_path := input_data.get("document_path"):
            content_parts.append(f"文档路径: {document_path}")
            # 注意：实际应用中这里应该读取文件内容
            # 这里简化处理
            content_parts.append("（文档内容已上传到知识库）")

        # 元数据中的文档内容
        if metadata := input_data.get("metadata"):
            if doc_id := metadata.get("document_id"):
                content_parts.append(f"文档ID: {doc_id}")

        # 相关知识点
        if related_knowledge := input_data.get("related_knowledge"):
            content_parts.append("\n相关知识点:")
            for i, knowledge in enumerate(related_knowledge[:3]):  # 只取前3个
                text = knowledge.get("text", "")[:200]  # 截断
                source = knowledge.get("source", "unknown")
                content_parts.append(f"{i+1}. [{source}] {text}...")

        return "\n".join(content_parts)

    async def _analyze_with_llm(self, prompt: str) -> Dict[str, Any]:
        """使用LLM分析需求"""
        try:
            # 调用LLM
            response = await self.call_llm(
                prompt=prompt,
                system_prompt="你是一个资深需求分析专家，专注于软件项目需求分析和规格定义。"
            )

            # 解析响应
            analysis_result = self._parse_llm_response(response)

            return analysis_result

        except Exception as e:
            logger.error(f"LLM分析失败: {str(e)}")
            # 回退到默认分析
            return self._fallback_analysis(prompt)

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """解析LLM响应"""
        try:
            # 尝试提取JSON部分
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试直接解析整个响应
                json_str = response.strip()

            # 解析JSON
            result = json.loads(json_str)

            # 确保字段存在
            return self._ensure_output_schema(result)

        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失败，尝试提取关键信息: {str(e)}")
            return self._extract_key_information(response)

    def _ensure_output_schema(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """确保输出符合模式"""
        # 复制默认模式
        validated_result = self.output_schema.copy()

        # 用实际结果更新
        for key, default_value in self.output_schema.items():
            if key in result:
                validated_result[key] = result[key]
            else:
                logger.warning(f"结果中缺少字段: {key}，使用默认值")

        return validated_result

    def _extract_key_information(self, text: str) -> Dict[str, Any]:
        """从文本中提取关键信息（回退方法）"""
        logger.info("使用回退方法提取关键信息")

        # 初始化结果
        result = self.output_schema.copy()

        # 简单提取
        lines = text.split('\n')

        # 尝试提取标题
        for line in lines:
            if "标题" in line or "Title" in line:
                parts = line.split(":", 1)
                if len(parts) > 1:
                    result["title"] = parts[1].strip()
                    break

        # 如果没有找到标题，使用前几行作为描述
        if result["title"] == "需求标题":
            for line in lines[:5]:
                if line.strip() and len(line.strip()) > 10:
                    result["description"] = line.strip() + "..."
                    break

        # 提取核心目标
        core_objectives = []
        in_objectives = False
        for line in lines:
            if "核心目标" in line or "Core Objectives" in line or "目标" in line:
                in_objectives = True
                continue

            if in_objectives and line.strip().startswith(("-", "•", "*", "1.", "2.", "3.")):
                objective = line.strip().lstrip("-•*123. ").strip()
                if objective and len(objective) > 5:
                    core_objectives.append(objective)

            if in_objectives and line.strip() == "" and core_objectives:
                break

        if core_objectives:
            result["core_objectives"] = core_objectives

        # 提取功能
        features = []
        in_features = False
        for line in lines:
            if "功能" in line or "Features" in line or "功能点" in line:
                in_features = True
                continue

            if in_features and line.strip().startswith(("-", "•", "*", "1.", "2.", "3.")):
                feature = line.strip().lstrip("-•*123. ").strip()
                if feature and len(feature) > 5:
                    features.append(feature)

            if in_features and line.strip() == "" and features:
                break

        if features:
            result["features"] = features

        return result

    def _fallback_analysis(self, prompt: str) -> Dict[str, Any]:
        """回退分析（当LLM失败时）"""
        logger.warning("使用回退分析")

        # 从提示中提取基本信息
        result = self.output_schema.copy()

        # 简单解析提示
        lines = prompt.split('\n')

        # 提取标题
        for line in lines:
            if "标题:" in line:
                result["title"] = line.split(":", 1)[1].strip()
                break

        # 提取描述
        for line in lines:
            if "描述:" in line:
                result["description"] = line.split(":", 1)[1].strip()
                break

        # 设置默认值
        if result["core_objectives"] == ["目标1", "目标2"]:
            result["core_objectives"] = ["完成需求分析", "生成详细规格"]

        if result["features"] == ["功能1", "功能2"]:
            result["features"] = ["需求分析功能", "规格生成功能"]

        if result["technical_constraints"] == ["约束1", "约束2"]:
            result["technical_constraints"] = ["系统稳定性", "安全性要求"]

        if result["assumptions"] == ["假设1", "假设2"]:
            result["assumptions"] = ["用户需求明确", "技术可行"]

        if result["suggested_tech_stack"] == ["技术1", "技术2"]:
            result["suggested_tech_stack"] = ["Python", "FastAPI", "PostgreSQL"]

        return result

    def _summarize_input(self, input_data: Dict[str, Any]) -> str:
        """摘要输入数据"""
        summary = []

        if title := input_data.get("title"):
            summary.append(f"标题: {title[:50]}...")

        if description := input_data.get("description"):
            desc_summary = description[:100] + "..." if len(description) > 100 else description
            summary.append(f"描述: {desc_summary}")

        if document_path := input_data.get("document_path"):
            summary.append(f"文档: {document_path}")

        if metadata := input_data.get("metadata"):
            if doc_id := metadata.get("document_id"):
                summary.append(f"文档ID: {doc_id}")

        return "; ".join(summary)

    def _get_current_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"

    async def get_analysis_template(self) -> Dict[str, Any]:
        """获取分析模板"""
        return {
            "template": self.prompt_template,
            "output_schema": self.output_schema,
            "config": {
                "max_retries": self.config.max_retries,
                "timeout": self.config.timeout,
                "temperature": self.config.temperature,
            }
        }