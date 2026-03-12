"""开发智能体

根据任务描述生成代码，支持多种编程语言。
"""

from typing import Dict, Any, List, Optional
import json
import re
import loguru

from .base_agent import BaseAgent
from config.agents_config import DevelopmentAgentConfig
from utils.llm_client import LLMClient

logger = loguru.logger


class DevelopmentAgent(BaseAgent):
    """开发智能体"""

    def __init__(
        self,
        name: str = "development_agent",
        config: Optional[DevelopmentAgentConfig] = None,
        llm_client: Optional[LLMClient] = None
    ):
        """初始化开发智能体"""
        config = config or DevelopmentAgentConfig()
        super().__init__(
            name=name,
            config=config,
            llm_client=llm_client
        )

        self.prompt_template = config.code_generation_prompt_template
        self.preferred_languages = config.preferred_languages
        self.include_tests = config.include_tests
        self.include_documentation = config.include_documentation

        logger.info(f"开发智能体初始化完成，支持语言: {self.preferred_languages}")

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理代码生成任务

        Args:
            input_data: 输入数据，包含任务描述、技术要求和代码上下文

        Returns:
            生成的代码和相关元数据
        """
        try:
            # 验证输入
            if not await self.validate_input(input_data):
                raise ValueError("输入数据验证失败")

            # 提取任务信息
            task_description = input_data.get("task_description", "")
            technical_requirements = input_data.get("technical_requirements", {})
            code_context = input_data.get("code_context", "")

            # 确定编程语言
            language = self._determine_language(technical_requirements, code_context)

            # 准备提示
            prompt = self._prepare_prompt(
                task_description=task_description,
                technical_requirements=technical_requirements,
                code_context=code_context,
                language=language
            )

            # 调用LLM生成代码
            system_prompt = self._prepare_system_prompt(language)
            generated_code = await self.call_llm(prompt, system_prompt=system_prompt)

            # 解析和验证生成的代码
            parsed_code = self._parse_generated_code(generated_code, language)

            # 生成测试代码（如果需要）
            test_code = {}
            if self.include_tests:
                test_code = await self._generate_tests(parsed_code, language)

            # 生成文档（如果需要）
            documentation = {}
            if self.include_documentation:
                documentation = await self._generate_documentation(parsed_code, language)

            # 计算质量指标
            quality_metrics = self._calculate_quality_metrics(parsed_code, language)

            # 准备输出
            output = {
                "status": "success",
                "generated_code": parsed_code,
                "language": language,
                "test_code": test_code,
                "documentation": documentation,
                "quality_metrics": quality_metrics,
                "metadata": {
                    "task_description": task_description,
                    "technical_requirements": technical_requirements,
                    "include_tests": self.include_tests,
                    "include_documentation": self.include_documentation,
                }
            }

            # 验证输出
            if not await self.validate_output(output):
                raise ValueError("输出数据验证失败")

            return output

        except Exception as e:
            logger.error(f"开发智能体处理失败: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "generated_code": {},
                "language": "unknown",
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

        # 检查必要字段
        required_fields = ["task_description"]
        for field in required_fields:
            if field not in input_data or not input_data[field]:
                logger.warning(f"开发智能体输入缺少必要字段: {field}")
                return False

        # 检查任务描述是否合理
        task_description = input_data.get("task_description", "")
        if len(task_description.strip()) < 10:
            logger.warning("开发智能体任务描述过短")
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
        required_fields = ["status", "generated_code", "language"]
        for field in required_fields:
            if field not in output_data:
                logger.warning(f"开发智能体输出缺少必要字段: {field}")
                return False

        # 检查状态
        if output_data["status"] not in ["success", "failed"]:
            logger.warning(f"开发智能体输出状态无效: {output_data['status']}")
            return False

        # 检查生成的代码
        if output_data["status"] == "success":
            generated_code = output_data.get("generated_code", {})
            if not generated_code or not isinstance(generated_code, dict):
                logger.warning("开发智能体生成的代码无效")
                return False

        return True

    def _determine_language(
        self,
        technical_requirements: Dict[str, Any],
        code_context: str
    ) -> str:
        """
        确定编程语言

        Args:
            technical_requirements: 技术要求
            code_context: 代码上下文

        Returns:
            编程语言
        """
        # 优先使用技术要求中指定的语言
        if "language" in technical_requirements:
            language = technical_requirements["language"]
            if language in self.preferred_languages:
                return language

        # 从代码上下文中推断语言
        if code_context:
            # 简单的语言检测
            language_patterns = {
                "python": [r"import\s+\w+", r"def\s+\w+\s*\(", r"class\s+\w+"],
                "javascript": [r"function\s+\w+\s*\(", r"const\s+\w+\s*=", r"let\s+\w+\s*="],
                "typescript": [r"interface\s+\w+", r"type\s+\w+\s*=", r"export\s+.*\s*{"],
                "java": [r"public\s+class\s+\w+", r"import\s+java\.", r"@Override"],
                "go": [r"func\s+\w+\s*\(", r"package\s+\w+", r"import\s+\("],
            }

            for lang, patterns in language_patterns.items():
                if lang in self.preferred_languages:
                    for pattern in patterns:
                        if re.search(pattern, code_context, re.IGNORECASE):
                            return lang

        # 默认返回首选语言列表中的第一个
        return self.preferred_languages[0] if self.preferred_languages else "python"

    def _prepare_prompt(
        self,
        task_description: str,
        technical_requirements: Dict[str, Any],
        code_context: str,
        language: str
    ) -> str:
        """
        准备提示

        Args:
            task_description: 任务描述
            technical_requirements: 技术要求
            code_context: 代码上下文
            language: 编程语言

        Returns:
            格式化后的提示
        """
        # 格式化技术要求
        tech_reqs_text = json.dumps(technical_requirements, indent=2, ensure_ascii=False)

        # 构建提示
        prompt = self.prompt_template.format(
            task_description=task_description,
            technical_requirements=tech_reqs_text,
            code_context=code_context,
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
        system_prompt = f"""你是一个资深的{language}开发专家。请根据以下要求生成高质量、可维护的代码：

1. 遵循{language}的最佳实践和编码规范
2. 代码结构清晰，有良好的模块化设计
3. 包含必要的错误处理和输入验证
4. 提供有意义的注释和文档
5. 考虑性能和安全性

请只返回代码，不要包含解释性文字。如果生成多个文件，请使用以下JSON格式：
{{
  "main.py": "代码内容",
  "utils.py": "代码内容",
  ...
}}

如果需要生成测试，请包含在单独的测试文件中。"""

        return system_prompt

    def _parse_generated_code(self, generated_text: str, language: str) -> Dict[str, str]:
        """
        解析生成的代码

        Args:
            generated_text: 生成的文本
            language: 编程语言

        Returns:
            解析后的代码字典（文件名 -> 代码内容）
        """
        try:
            # 尝试解析为JSON
            if generated_text.strip().startswith("{"):
                code_data = json.loads(generated_text)
                if isinstance(code_data, dict):
                    # 验证所有值都是字符串
                    valid_code_data = {}
                    for filename, content in code_data.items():
                        if isinstance(content, str):
                            valid_code_data[filename] = content
                        else:
                            valid_code_data[filename] = str(content)
                    return valid_code_data
        except json.JSONDecodeError:
            pass

        # 如果不是JSON格式，假设是单个代码文件
        # 根据语言确定文件名
        file_extensions = {
            "python": ".py",
            "javascript": ".js",
            "typescript": ".ts",
            "java": ".java",
            "go": ".go",
        }

        extension = file_extensions.get(language, ".txt")
        filename = f"main{extension}"

        return {filename: generated_text}

    async def _generate_tests(
        self,
        code_data: Dict[str, str],
        language: str
    ) -> Dict[str, str]:
        """
        生成测试代码

        Args:
            code_data: 生成的代码
            language: 编程语言

        Returns:
            测试代码字典
        """
        try:
            # 这里可以调用专门的测试生成智能体
            # 暂时返回简单的测试占位符
            test_files = {}

            for filename, content in code_data.items():
                test_filename = self._get_test_filename(filename, language)
                test_content = f"""# 测试文件: {test_filename}
# 待实现: 为 {filename} 生成测试用例
# 语言: {language}

import unittest

class Test{filename.replace('.', '_')}(unittest.TestCase):
    def test_example(self):
        self.assertTrue(True)

if __name__ == '__main__':
    unittest.main()
"""
                test_files[test_filename] = test_content

            return test_files

        except Exception as e:
            logger.error(f"生成测试代码失败: {e}")
            return {}

    def _get_test_filename(self, filename: str, language: str) -> str:
        """获取测试文件名"""
        import os

        name, ext = os.path.splitext(filename)
        test_suffixes = {
            "python": "_test.py",
            "javascript": ".test.js",
            "typescript": ".test.ts",
            "java": "Test.java",
            "go": "_test.go",
        }

        test_suffix = test_suffixes.get(language, "_test.txt")
        return f"{name}{test_suffix}"

    async def _generate_documentation(
        self,
        code_data: Dict[str, str],
        language: str
    ) -> Dict[str, str]:
        """
        生成文档

        Args:
            code_data: 生成的代码
            language: 编程语言

        Returns:
            文档字典
        """
        try:
            documentation = {}

            for filename, content in code_data.items():
                doc_filename = f"README_{filename}.md"
                doc_content = f"""# {filename} 文档

## 文件说明
- 语言: {language}
- 文件: {filename}

## 功能概述
此文件包含自动生成的代码，具体功能请参考代码实现。

## 使用方法
```{language}
# 示例用法待补充
```

## API参考
主要函数和类：
- 待补充

## 注意事项
1. 这是自动生成的代码，建议进行人工审查
2. 确保满足所有业务需求
3. 添加适当的错误处理
"""
                documentation[doc_filename] = doc_content

            return documentation

        except Exception as e:
            logger.error(f"生成文档失败: {e}")
            return {}

    def _calculate_quality_metrics(
        self,
        code_data: Dict[str, str],
        language: str
    ) -> Dict[str, Any]:
        """
        计算质量指标

        Args:
            code_data: 生成的代码
            language: 编程语言

        Returns:
            质量指标
        """
        # 简化的质量评估
        total_lines = 0
        total_files = len(code_data)
        has_comments = False

        for content in code_data.values():
            lines = content.split('\n')
            total_lines += len(lines)

            # 检查是否有注释
            for line in lines:
                stripped_line = line.strip()
                if stripped_line.startswith('#') or stripped_line.startswith('//') or stripped_line.startswith('/*'):
                    has_comments = True
                    break

        # 计算质量分数（简化版本）
        quality_score = 70  # 基础分数

        if has_comments:
            quality_score += 10

        if total_files > 1:
            quality_score += 5  # 多个文件通常表示更好的模块化

        if total_lines > 0 and total_lines < 500:
            quality_score += 5  # 适中的代码量
        elif total_lines >= 500:
            quality_score -= 5  # 代码量过大

        # 确保分数在合理范围内
        quality_score = max(0, min(100, quality_score))

        return {
            "score": quality_score,
            "total_files": total_files,
            "total_lines": total_lines,
            "has_comments": has_comments,
            "language": language,
        }

    def get_status(self) -> Dict[str, Any]:
        """
        获取智能体状态

        Returns:
            状态信息
        """
        base_status = super().get_status()
        base_status.update({
            "preferred_languages": self.preferred_languages,
            "include_tests": self.include_tests,
            "include_documentation": self.include_documentation,
        })
        return base_status