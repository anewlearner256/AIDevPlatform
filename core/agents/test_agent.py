"""测试智能体

为代码生成测试用例，支持多种测试框架。
"""

from typing import Dict, Any, List, Optional
import json
import re
import loguru

from .base_agent import BaseAgent
from config.agents_config import TestAgentConfig
from utils.llm_client import LLMClient

logger = loguru.logger


class TestAgent(BaseAgent):
    """测试智能体"""

    def __init__(
        self,
        name: str = "test_agent",
        config: Optional[TestAgentConfig] = None,
        llm_client: Optional[LLMClient] = None
    ):
        """初始化测试智能体"""
        config = config or TestAgentConfig()
        super().__init__(
            name=name,
            config=config,
            llm_client=llm_client
        )

        self.prompt_template = config.test_generation_prompt_template
        self.test_framework = config.test_framework
        self.min_test_coverage = config.min_test_coverage

        logger.info(f"测试智能体初始化完成，测试框架: {self.test_framework}")

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理测试生成任务

        Args:
            input_data: 输入数据，包含代码和功能描述

        Returns:
            生成的测试用例和相关元数据
        """
        try:
            # 验证输入
            if not await self.validate_input(input_data):
                raise ValueError("输入数据验证失败")

            # 提取测试信息
            code = input_data.get("code", {})
            function_description = input_data.get("function_description", "")
            test_requirements = input_data.get("test_requirements", [])

            # 准备代码文本
            code_text = self._prepare_code_text(code)

            # 确定代码语言
            language = self._detect_language(code)

            # 准备提示
            prompt = self._prepare_prompt(
                code_text=code_text,
                function_description=function_description,
                test_requirements=test_requirements,
                language=language
            )

            # 准备系统提示
            system_prompt = self._prepare_system_prompt(language)

            # 调用LLM生成测试
            generated_tests = await self.call_llm(prompt, system_prompt=system_prompt)

            # 解析生成的测试
            test_cases = self._parse_generated_tests(generated_tests, language)

            # 计算测试覆盖率估计
            coverage_estimate = self._estimate_coverage(test_cases, code_text)

            # 评估测试质量
            test_quality = self._evaluate_test_quality(test_cases, test_requirements)

            # 准备输出
            output = {
                "status": "success",
                "test_cases": test_cases,
                "test_framework": self.test_framework,
                "language": language,
                "coverage_estimate": coverage_estimate,
                "test_quality": test_quality,
                "metadata": {
                    "function_description": function_description,
                    "test_requirements": test_requirements,
                    "min_test_coverage": self.min_test_coverage,
                }
            }

            # 验证输出
            if not await self.validate_output(output):
                raise ValueError("输出数据验证失败")

            return output

        except Exception as e:
            logger.error(f"测试智能体处理失败: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "test_cases": [],
                "test_framework": self.test_framework,
                "language": "unknown",
                "coverage_estimate": 0,
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
            logger.warning("测试智能体输入缺少代码")
            return False

        # 检查至少有一个代码文件
        if len(code) == 0:
            logger.warning("测试智能体输入代码为空")
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
        required_fields = ["status", "test_cases", "test_framework", "language", "coverage_estimate"]
        for field in required_fields:
            if field not in output_data:
                logger.warning(f"测试智能体输出缺少必要字段: {field}")
                return False

        # 检查状态
        if output_data["status"] not in ["success", "failed"]:
            logger.warning(f"测试智能体输出状态无效: {output_data['status']}")
            return False

        # 检查测试用例
        if output_data["status"] == "success":
            test_cases = output_data.get("test_cases", [])
            if not isinstance(test_cases, list):
                logger.warning("测试智能体测试用例不是列表")
                return False

        # 检查覆盖率
        coverage = output_data.get("coverage_estimate", 0)
        if not isinstance(coverage, (int, float)) or coverage < 0 or coverage > 100:
            logger.warning(f"测试智能体覆盖率估计无效: {coverage}")
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

    def _detect_language(self, code: Dict[str, str]) -> str:
        """
        检测编程语言

        Args:
            code: 代码字典

        Returns:
            编程语言
        """
        # 检查文件名后缀
        file_extensions = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".java": "java",
            ".go": "go",
            ".cpp": "cpp",
            ".c": "c",
            ".rb": "ruby",
            ".php": "php",
        }

        for filename in code.keys():
            for ext, lang in file_extensions.items():
                if filename.endswith(ext):
                    return lang

        # 如果无法从扩展名判断，检查代码内容
        sample_code = next(iter(code.values())) if code else ""

        language_patterns = {
            "python": [r"import\s+\w+", r"def\s+\w+\s*\(", r"class\s+\w+"],
            "javascript": [r"function\s+\w+\s*\(", r"const\s+\w+\s*=", r"let\s+\w+\s*="],
            "typescript": [r"interface\s+\w+", r"type\s+\w+\s*=", r"export\s+.*\s*{"],
            "java": [r"public\s+class\s+\w+", r"import\s+java\.", r"@Override"],
            "go": [r"func\s+\w+\s*\(", r"package\s+\w+", r"import\s+\("],
        }

        for lang, patterns in language_patterns.items():
            for pattern in patterns:
                if re.search(pattern, sample_code, re.IGNORECASE):
                    return lang

        return "python"  # 默认返回Python

    def _prepare_prompt(
        self,
        code_text: str,
        function_description: str,
        test_requirements: List[str],
        language: str
    ) -> str:
        """
        准备提示

        Args:
            code_text: 代码文本
            function_description: 功能描述
            test_requirements: 测试要求
            language: 编程语言

        Returns:
            格式化后的提示
        """
        # 格式化测试要求
        if test_requirements:
            requirements_text = "\n".join([f"- {req}" for req in test_requirements])
        else:
            requirements_text = "无特定要求"

        # 构建提示
        prompt = self.prompt_template.format(
            code=code_text,
            function_description=function_description,
            test_requirements=requirements_text,
            language=language
        )

        return prompt

    def _prepare_system_prompt(self, language: str) -> str:
        """
        准备系统提示

        Args:
            language: 编程语言

        Returns:
            系统提示
        """
        # 测试框架映射
        framework_info = {
            "python": "pytest",
            "javascript": "jest",
            "typescript": "jest",
            "java": "junit",
            "go": "testing",
        }

        framework = framework_info.get(language, self.test_framework)

        system_prompt = f"""你是一个资深的测试专家，专门为{language}代码生成测试用例。

请使用{framework}测试框架，生成全面的测试用例，包括：

1. 单元测试：测试单个函数或方法
2. 边界条件测试：测试输入边界和极端情况
3. 异常处理测试：测试错误和异常情况
4. 集成测试：测试多个组件的交互

请严格按照以下格式返回测试用例：
{{
  "test_cases": [
    {{
      "name": "测试用例名称",
      "type": "unit/boundary/exception/integration",
      "description": "测试描述",
      "code": "测试代码",
      "expected_result": "预期结果"
    }}
  ],
  "summary": "测试用例总结"
}}

请确保：
1. 测试用例名称具有描述性
2. 测试代码语法正确
3. 包含必要的断言
4. 覆盖所有重要的功能和边界条件
5. 总结简明扼要"""

        return system_prompt

    def _parse_generated_tests(self, generated_text: str, language: str) -> List[Dict[str, Any]]:
        """
        解析生成的测试

        Args:
            generated_text: 生成的测试文本
            language: 编程语言

        Returns:
            解析后的测试用例列表
        """
        try:
            # 尝试解析为JSON
            if generated_text.strip().startswith("{"):
                test_data = json.loads(generated_text)
                if isinstance(test_data, dict) and "test_cases" in test_data:
                    test_cases = test_data["test_cases"]
                    if isinstance(test_cases, list):
                        # 验证测试用例格式
                        valid_cases = []
                        for test_case in test_cases:
                            if isinstance(test_case, dict) and "name" in test_case and "code" in test_case:
                                valid_cases.append(test_case)
                        return valid_cases
        except json.JSONDecodeError:
            pass

        # 如果不是JSON格式，尝试解析为结构化文本
        test_cases = []
        lines = generated_text.split('\n')
        current_test = None
        in_test_code = False
        test_code = []

        for line in lines:
            line = line.strip()

            # 检测测试用例开始
            if line.lower().startswith("test:") or line.lower().startswith("测试:"):
                if current_test and test_code:
                    current_test["code"] = "\n".join(test_code)
                    test_cases.append(current_test)

                # 提取测试名称
                if line.lower().startswith("test:"):
                    test_name = line[5:].strip()
                else:
                    test_name = line[3:].strip()

                current_test = {
                    "name": test_name,
                    "type": "unit",
                    "description": "",
                    "code": "",
                    "expected_result": "",
                }
                test_code = []
                in_test_code = False

            # 检测描述
            elif line.lower().startswith("description:") or line.lower().startswith("描述:"):
                if current_test:
                    if line.lower().startswith("description:"):
                        current_test["description"] = line[12:].strip()
                    else:
                        current_test["description"] = line[3:].strip()

            # 检测预期结果
            elif line.lower().startswith("expected:") or line.lower().startswith("预期:"):
                if current_test:
                    if line.lower().startswith("expected:"):
                        current_test["expected_result"] = line[9:].strip()
                    else:
                        current_test["expected_result"] = line[3:].strip()

            # 检测代码块开始
            elif line.startswith("```") or line.startswith("代码:"):
                in_test_code = True
                test_code = []

            # 检测代码块结束
            elif line.endswith("```") and in_test_code:
                in_test_code = False
                if current_test:
                    current_test["code"] = "\n".join(test_code)

            # 在代码块中
            elif in_test_code:
                test_code.append(line)

            # 其他文本作为描述的一部分
            elif current_test and line and not line.startswith("-"):
                if not current_test["description"]:
                    current_test["description"] = line
                else:
                    current_test["description"] += " " + line

        # 添加最后一个测试用例
        if current_test and test_code:
            current_test["code"] = "\n".join(test_code)
            test_cases.append(current_test)

        return test_cases

    def _estimate_coverage(self, test_cases: List[Dict[str, Any]], code_text: str) -> float:
        """
        估计测试覆盖率

        Args:
            test_cases: 测试用例列表
            code_text: 代码文本

        Returns:
            覆盖率估计 (0-100)
        """
        if not test_cases:
            return 0

        # 简化的覆盖率估计
        # 基于测试用例数量和类型
        unit_test_count = sum(1 for test in test_cases if test.get("type") == "unit")
        boundary_test_count = sum(1 for test in test_cases if test.get("type") == "boundary")
        exception_test_count = sum(1 for test in test_cases if test.get("type") == "exception")
        integration_test_count = sum(1 for test in test_cases if test.get("type") == "integration")

        # 计算基础覆盖率
        base_coverage = min(100, unit_test_count * 10)  # 每个单元测试增加10%

        # 不同类型测试的权重
        coverage_adjustments = {
            "boundary": boundary_test_count * 5,    # 每个边界测试增加5%
            "exception": exception_test_count * 8,  # 每个异常测试增加8%
            "integration": integration_test_count * 7,  # 每个集成测试增加7%
        }

        # 应用调整
        total_coverage = base_coverage
        for adjustment in coverage_adjustments.values():
            total_coverage = min(100, total_coverage + adjustment)

        # 基于代码复杂度的调整
        code_lines = len(code_text.split('\n'))
        if code_lines > 200:
            total_coverage = max(0, total_coverage - 10)  # 复杂代码降低覆盖率估计
        elif code_lines < 50:
            total_coverage = min(100, total_coverage + 10)  # 简单代码提高覆盖率估计

        return round(total_coverage, 1)

    def _evaluate_test_quality(self, test_cases: List[Dict[str, Any]], test_requirements: List[str]) -> Dict[str, Any]:
        """
        评估测试质量

        Args:
            test_cases: 测试用例列表
            test_requirements: 测试要求

        Returns:
            质量评估结果
        """
        if not test_cases:
            return {
                "score": 0,
                "issues": ["没有生成测试用例"],
                "strengths": [],
                "recommendations": ["生成基本的单元测试"],
            }

        # 计算质量分数
        base_score = 60

        # 测试用例数量
        test_count = len(test_cases)
        if test_count >= 10:
            base_score += 20
        elif test_count >= 5:
            base_score += 10
        elif test_count >= 3:
            base_score += 5

        # 测试类型多样性
        test_types = set(test.get("type", "unit") for test in test_cases)
        type_count = len(test_types)
        base_score += type_count * 5

        # 检查测试要求满足情况
        requirements_met = 0
        if test_requirements:
            for requirement in test_requirements:
                req_lower = requirement.lower()
                # 检查是否有测试用例满足要求
                for test_case in test_cases:
                    if (req_lower in test_case.get("name", "").lower() or
                        req_lower in test_case.get("description", "").lower() or
                        req_lower in test_case.get("type", "").lower()):
                        requirements_met += 1
                        break

            if test_requirements:
                requirement_coverage = (requirements_met / len(test_requirements)) * 100
                base_score += requirement_coverage * 0.2

        # 检查测试用例质量
        quality_issues = []
        strengths = []
        recommendations = []

        for i, test_case in enumerate(test_cases):
            # 检查必要字段
            if not test_case.get("code"):
                quality_issues.append(f"测试用例 {i+1} 缺少代码")
            if not test_case.get("expected_result"):
                quality_issues.append(f"测试用例 {i+1} 缺少预期结果")

            # 检查代码质量
            code = test_case.get("code", "")
            if "assert" in code or "expect" in code or "should" in code:
                strengths.append(f"测试用例 {i+1} 包含断言")
            else:
                recommendations.append(f"测试用例 {i+1} 应添加断言")

        # 根据问题调整分数
        issue_penalty = len(quality_issues) * 5
        base_score = max(0, base_score - issue_penalty)

        # 确保分数在合理范围内
        final_score = min(100, max(0, round(base_score)))

        return {
            "score": final_score,
            "issues": quality_issues,
            "strengths": strengths,
            "recommendations": recommendations,
            "test_count": test_count,
            "test_types": list(test_types),
            "requirements_met": f"{requirements_met}/{len(test_requirements) if test_requirements else 0}",
        }

    def get_status(self) -> Dict[str, Any]:
        """
        获取智能体状态

        Returns:
            状态信息
        """
        base_status = super().get_status()
        base_status.update({
            "test_framework": self.test_framework,
            "min_test_coverage": self.min_test_coverage,
        })
        return base_status