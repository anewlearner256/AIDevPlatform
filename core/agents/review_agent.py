"""评审智能体

评审代码质量，检查安全性、性能和最佳实践。
"""

from typing import Dict, Any, List, Optional
import json
import re
import loguru

from .base_agent import BaseAgent
from config.agents_config import ReviewAgentConfig
from utils.llm_client import LLMClient

logger = loguru.logger


class ReviewAgent(BaseAgent):
    """评审智能体"""

    def __init__(
        self,
        name: str = "review_agent",
        config: Optional[ReviewAgentConfig] = None,
        llm_client: Optional[LLMClient] = None
    ):
        """初始化评审智能体"""
        config = config or ReviewAgentConfig()
        super().__init__(
            name=name,
            config=config,
            llm_client=llm_client
        )

        self.prompt_template = config.review_prompt_template
        self.check_security = config.check_security
        self.check_performance = config.check_performance
        self.check_best_practices = config.check_best_practices

        logger.info(f"评审智能体初始化完成，安全检查: {self.check_security}, 性能检查: {self.check_performance}")

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理代码评审

        Args:
            input_data: 输入数据，包含代码和评审上下文

        Returns:
            评审结果和改进建议
        """
        try:
            # 验证输入
            if not await self.validate_input(input_data):
                raise ValueError("输入数据验证失败")

            # 提取评审信息
            code = input_data.get("code", {})
            check_type = input_data.get("check_type", "comprehensive")
            code_metadata = input_data.get("code_metadata", {})

            # 准备代码文本
            code_text = self._prepare_code_text(code)

            # 根据检查类型准备不同的提示
            if check_type == "security":
                prompt = self._prepare_security_prompt(code_text)
            elif check_type == "performance":
                prompt = self._prepare_performance_prompt(code_text)
            elif check_type == "quality":
                prompt = self._prepare_quality_prompt(code_text)
            else:
                prompt = self._prepare_comprehensive_prompt(code_text)

            # 准备系统提示
            system_prompt = self._prepare_system_prompt(check_type)

            # 调用LLM进行评审
            review_text = await self.call_llm(prompt, system_prompt=system_prompt)

            # 解析评审结果
            review_result = self._parse_review_result(review_text, check_type)

            # 计算质量分数
            quality_score = self._calculate_quality_score(review_result, check_type)

            # 检查是否需要进一步的安全或性能检查
            needs_security_check = self.check_security and self._needs_security_check(review_result)
            needs_performance_check = self.check_performance and self._needs_performance_check(review_result)

            # 准备输出
            output = {
                "status": "success",
                "review_result": review_result,
                "quality_score": quality_score,
                "check_type": check_type,
                "needs_security_check": needs_security_check,
                "needs_performance_check": needs_performance_check,
                "issues_found": len(review_result.get("issues", [])),
                "suggestions": review_result.get("suggestions", []),
                "metadata": {
                    "code_metadata": code_metadata,
                    "check_security": self.check_security,
                    "check_performance": self.check_performance,
                    "check_best_practices": self.check_best_practices,
                }
            }

            # 验证输出
            if not await self.validate_output(output):
                raise ValueError("输出数据验证失败")

            return output

        except Exception as e:
            logger.error(f"评审智能体处理失败: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "review_result": {},
                "quality_score": 0,
                "check_type": input_data.get("check_type", "comprehensive"),
            }

    async def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """
        验证输入数据

        Args:
            input_data: 输入数据

        Returns:
            是否有效
        """
        # 调用父类的基础验证
        if not await super().validate_input(input_data):
            return False

        # 检查代码
        code = input_data.get("code", {})
        if not code or not isinstance(code, dict):
            logger.warning("评审智能体输入缺少代码")
            return False

        # 检查至少有一个代码文件
        if len(code) == 0:
            logger.warning("评审智能体输入代码为空")
            return False

        return True

    async def validate_output(self, output_data: Dict[str, Any]) -> bool:
        """
        验证输出数据

        Args:
            output_data: 输出数据

        Returns:
            是否有效
        """
        # 调用父类的基础验证
        if not await super().validate_output(output_data):
            return False

        # 检查必要字段
        required_fields = ["status", "review_result", "quality_score", "check_type"]
        for field in required_fields:
            if field not in output_data:
                logger.warning(f"评审智能体输出缺少必要字段: {field}")
                return False

        # 检查状态
        if output_data["status"] not in ["success", "failed"]:
            logger.warning(f"评审智能体输出状态无效: {output_data['status']}")
            return False

        # 检查质量分数
        quality_score = output_data.get("quality_score", 0)
        if not isinstance(quality_score, (int, float)) or quality_score < 0 or quality_score > 100:
            logger.warning(f"评审智能体质量分数无效: {quality_score}")
            return False

        return True

    def _prepare_code_text(self, code: Dict[str, str]) -> str:
        """
        准备代码文本

        Args:
            code: 代码字典（文件名 -> 代码内容）

        Returns:
            格式化后的代码文本
        """
        code_text = ""

        for filename, content in code.items():
            code_text += f"文件: {filename}\n"
            code_text += "=" * 50 + "\n"
            code_text += content + "\n"
            code_text += "=" * 50 + "\n\n"

        return code_text

    def _prepare_comprehensive_prompt(self, code_text: str) -> str:
        """准备综合评审提示"""
        prompt = self.prompt_template.format(code=code_text)
        return prompt

    def _prepare_security_prompt(self, code_text: str) -> str:
        """准备安全评审提示"""
        prompt = f"""请从安全角度评审以下代码，特别关注：

1. 输入验证和清理
2. 注入攻击（SQL、命令、模板等）
3. 认证和授权问题
4. 敏感数据泄露
5. 加密和密钥管理
6. 会话管理
7. 跨站脚本（XSS）和跨站请求伪造（CSRF）
8. 不安全的依赖项

请提供具体的安全问题和改进建议。

代码：
{code_text}
"""
        return prompt

    def _prepare_performance_prompt(self, code_text: str) -> str:
        """准备性能评审提示"""
        prompt = f"""请从性能角度评审以下代码，特别关注：

1. 算法复杂度
2. 内存使用和泄漏
3. 数据库查询优化
4. 网络请求优化
5. 缓存策略
6. 并发和并行处理
7. I/O操作优化
8. 资源管理

请提供具体的性能问题和改进建议。

代码：
{code_text}
"""
        return prompt

    def _prepare_quality_prompt(self, code_text: str) -> str:
        """准备质量评审提示"""
        prompt = f"""请从代码质量角度评审以下代码，特别关注：

1. 可读性和可维护性
2. 代码结构和组织
3. 命名规范
4. 注释和文档
5. 错误处理
6. 测试覆盖
7. 代码重复
8. 复杂性

请提供具体的质量问题和改进建议。

代码：
{code_text}
"""
        return prompt

    def _prepare_system_prompt(self, check_type: str) -> str:
        """
        准备系统提示

        Args:
            check_type: 检查类型

        Returns:
            系统提示
        """
        check_type_names = {
            "security": "安全",
            "performance": "性能",
            "quality": "质量",
            "comprehensive": "综合",
        }

        check_name = check_type_names.get(check_type, "综合")

        system_prompt = f"""你是一个资深的代码评审专家，专门进行{check_name}评审。

请严格按照以下格式返回评审结果：
{{
  "issues": [
    {{
      "type": "问题类型",
      "severity": "low/medium/high/critical",
      "description": "问题描述",
      "location": "文件:行号",
      "recommendation": "改进建议"
    }}
  ],
  "suggestions": [
    "具体的改进建议1",
    "具体的改进建议2"
  ],
  "summary": "评审总结"
}}

请确保：
1. 问题描述具体明确
2. 严重程度评估准确
3. 改进建议具有可操作性
4. 总结简明扼要"""

        return system_prompt

    def _parse_review_result(self, review_text: str, check_type: str) -> Dict[str, Any]:
        """
        解析评审结果

        Args:
            review_text: 评审文本
            check_type: 检查类型

        Returns:
            解析后的评审结果
        """
        try:
            # 尝试解析为JSON
            if review_text.strip().startswith("{"):
                result = json.loads(review_text)
                if isinstance(result, dict):
                    return result
        except json.JSONDecodeError:
            pass

        # 如果不是JSON格式，创建结构化的结果
        issues = []
        suggestions = []

        # 尝试从文本中提取信息
        lines = review_text.split('\n')
        current_issue = None

        for line in lines:
            line = line.strip()

            # 检测问题行
            if line.lower().startswith(("问题:", "issue:", "bug:", "vulnerability:")):
                if current_issue:
                    issues.append(current_issue)
                current_issue = {
                    "type": check_type,
                    "severity": "medium",
                    "description": line,
                    "location": "未知",
                    "recommendation": "",
                }
            elif line.lower().startswith("建议:") or line.lower().startswith("suggestion:"):
                if line.lower().startswith("建议:"):
                    suggestion = line[3:].strip()
                else:
                    suggestion = line[11:].strip()
                if suggestion:
                    suggestions.append(suggestion)
                if current_issue:
                    current_issue["recommendation"] = suggestion
            elif current_issue and line and not line.startswith("-"):
                # 添加到问题描述
                current_issue["description"] += " " + line

        # 添加最后一个问题
        if current_issue:
            issues.append(current_issue)

        # 创建总结
        issue_count = len(issues)
        if issue_count == 0:
            summary = "代码质量良好，未发现明显问题。"
        elif issue_count <= 3:
            summary = f"发现 {issue_count} 个问题，建议进行改进。"
        else:
            summary = f"发现 {issue_count} 个问题，代码需要重构和改进。"

        return {
            "issues": issues,
            "suggestions": suggestions,
            "summary": summary,
        }

    def _calculate_quality_score(self, review_result: Dict[str, Any], check_type: str) -> float:
        """
        计算质量分数

        Args:
            review_result: 评审结果
            check_type: 检查类型

        Returns:
            质量分数 (0-100)
        """
        # 基础分数
        base_score = 80

        # 根据问题数量和严重程度调整分数
        issues = review_result.get("issues", [])
        issue_count = len(issues)

        # 计算严重程度权重
        severity_weights = {
            "critical": 10,
            "high": 5,
            "medium": 2,
            "low": 1,
        }

        severity_score = 0
        for issue in issues:
            severity = issue.get("severity", "medium").lower()
            severity_score += severity_weights.get(severity, 2)

        # 调整分数
        adjusted_score = base_score - (issue_count * 2) - (severity_score * 1)

        # 确保分数在合理范围内
        adjusted_score = max(0, min(100, adjusted_score))

        # 根据检查类型调整
        if check_type == "security" and issue_count == 0:
            adjusted_score = min(100, adjusted_score + 10)  # 无安全问题加分
        elif check_type == "performance" and issue_count == 0:
            adjusted_score = min(100, adjusted_score + 5)  # 无性能问题加分

        return round(adjusted_score, 1)

    def _needs_security_check(self, review_result: Dict[str, Any]) -> bool:
        """检查是否需要安全评审"""
        if not self.check_security:
            return False

        issues = review_result.get("issues", [])
        for issue in issues:
            issue_type = issue.get("type", "").lower()
            if any(keyword in issue_type for keyword in ["security", "injection", "auth", "xss", "csrf"]):
                return True

        # 检查是否有高风险问题
        for issue in issues:
            severity = issue.get("severity", "").lower()
            if severity in ["critical", "high"]:
                return True

        return False

    def _needs_performance_check(self, review_result: Dict[str, Any]) -> bool:
        """检查是否需要性能评审"""
        if not self.check_performance:
            return False

        issues = review_result.get("issues", [])
        for issue in issues:
            issue_type = issue.get("type", "").lower()
            if any(keyword in issue_type for keyword in ["performance", "memory", "cpu", "optimization", "complexity"]):
                return True

        # 检查是否有复杂算法或大量数据处理
        for issue in issues:
            description = issue.get("description", "").lower()
            if any(keyword in description for keyword in ["nested loop", "exponential", "large data", "memory leak"]):
                return True

        return False

    def get_status(self) -> Dict[str, Any]:
        """
        获取智能体状态

        Returns:
            状态信息
        """
        base_status = super().get_status()
        base_status.update({
            "check_security": self.check_security,
            "check_performance": self.check_performance,
            "check_best_practices": self.check_best_practices,
        })
        return base_status