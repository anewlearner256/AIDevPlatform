"""LLM客户端

封装Claude和OpenAI API调用，提供统一的接口。
"""

import asyncio
from typing import Optional, Dict, Any, List
import anthropic
from openai import OpenAI, AsyncOpenAI
import loguru
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings
from config.llm_config import LLMConfig, LLMProvider, LLM_CONFIGS

logger = loguru.logger

class LLMClient:
    """LLM客户端"""

    _instances: Dict[str, "LLMClient"] = {}

    def __init__(self, config_name: str = "default"):
        """
        初始化LLM客户端

        Args:
            config_name: 配置名称
        """
        self.config = LLM_CONFIGS.get(config_name, LLMConfig())
        self._claude_client = None
        self._openai_client = None
        self._async_openai_client = None

        logger.info(f"初始化LLM客户端: {self.config.provider}/{self.config.model}")

    @classmethod
    def get_default(cls) -> "LLMClient":
        """获取默认LLM客户端"""
        return cls.get_instance("default")

    @classmethod
    def get_instance(cls, config_name: str = "default") -> "LLMClient":
        """获取LLM客户端实例（单例模式）"""
        if config_name not in cls._instances:
            cls._instances[config_name] = cls(config_name)
        return cls._instances[config_name]

    def get_claude_client(self) -> anthropic.Anthropic:
        """获取Claude客户端"""
        if self._claude_client is None:
            if not settings.claude_api_key:
                raise ValueError("Claude API密钥未配置")
            self._claude_client = anthropic.Anthropic(api_key=settings.claude_api_key)
        return self._claude_client

    def get_openai_client(self) -> OpenAI:
        """获取OpenAI客户端（同步）"""
        if self._openai_client is None:
            if not settings.openai_api_key:
                raise ValueError("OpenAI API密钥未配置")
            self._openai_client = OpenAI(api_key=settings.openai_api_key)
        return self._openai_client

    def get_async_openai_client(self) -> AsyncOpenAI:
        """获取OpenAI客户端（异步）"""
        if self._async_openai_client is None:
            if not settings.openai_api_key:
                raise ValueError("OpenAI API密钥未配置")
            self._async_openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._async_openai_client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        生成文本

        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            **kwargs: 其他参数（temperature, max_tokens等）

        Returns:
            生成的文本
        """
        # 合并配置参数
        params = {
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            **kwargs
        }

        try:
            if self.config.provider == LLMProvider.CLAUDE:
                return await self._generate_claude(prompt, system_prompt, **params)
            elif self.config.provider == LLMProvider.OPENAI:
                return await self._generate_openai(prompt, system_prompt, **params)
            elif self.config.provider == LLMProvider.AZURE_OPENAI:
                return await self._generate_azure_openai(prompt, system_prompt, **params)
            else:
                raise ValueError(f"不支持的LLM提供商: {self.config.provider}")

        except Exception as e:
            logger.error(f"LLM生成失败: {str(e)}")
            raise

    async def _generate_claude(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """使用Claude生成文本"""
        client = self.get_claude_client()

        # 准备消息
        messages = [{"role": "user", "content": prompt}]

        # 调用API
        response = client.messages.create(
            model=self.config.model,
            messages=messages,
            system=system_prompt,
            **kwargs
        )

        # 提取文本内容
        if response.content and len(response.content) > 0:
            content_block = response.content[0]
            if hasattr(content_block, 'text'):
                return content_block.text
            elif isinstance(content_block, dict) and 'text' in content_block:
                return content_block['text']
            else:
                return str(content_block)
        else:
            return ""

    async def _generate_openai(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """使用OpenAI生成文本"""
        client = self.get_async_openai_client()

        # 准备消息
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # 调用API
        response = await client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            **kwargs
        )

        # 提取文本内容
        if response.choices and len(response.choices) > 0:
            return response.choices[0].message.content or ""
        else:
            return ""

    async def _generate_azure_openai(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """使用Azure OpenAI生成文本"""
        # 简化实现，实际中需要处理Azure特定配置
        # 这里回退到标准OpenAI
        logger.warning("Azure OpenAI未完全实现，使用标准OpenAI")
        return await self._generate_openai(prompt, system_prompt, **kwargs)

    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        生成JSON格式的响应

        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            **kwargs: 其他参数

        Returns:
            JSON解析后的字典
        """
        # 添加JSON格式要求
        json_prompt = f"{prompt}\n\n请以JSON格式返回结果。"

        try:
            response_text = await self.generate(json_prompt, system_prompt, **kwargs)

            # 提取JSON部分（可能在代码块中）
            import json
            import re

            # 查找JSON代码块
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试直接解析整个响应
                json_str = response_text.strip()

            # 解析JSON
            return json.loads(json_str)

        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {str(e)}，响应文本: {response_text[:200]}...")
            raise ValueError(f"无法解析LLM响应为JSON: {str(e)}")
        except Exception as e:
            logger.error(f"生成JSON失败: {str(e)}")
            raise

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ):
        """
        流式生成文本

        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            **kwargs: 其他参数

        Yields:
            生成的文本块
        """
        # 合并配置参数
        params = {
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            **kwargs
        }

        try:
            if self.config.provider == LLMProvider.CLAUDE:
                async for chunk in self._generate_stream_claude(prompt, system_prompt, **params):
                    yield chunk
            elif self.config.provider == LLMProvider.OPENAI:
                async for chunk in self._generate_stream_openai(prompt, system_prompt, **params):
                    yield chunk
            else:
                raise ValueError(f"不支持的LLM提供商: {self.config.provider}")

        except Exception as e:
            logger.error(f"流式生成失败: {str(e)}")
            raise

    async def _generate_stream_claude(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ):
        """使用Claude流式生成文本"""
        client = self.get_claude_client()

        # 准备消息
        messages = [{"role": "user", "content": prompt}]

        # 调用流式API
        with client.messages.stream(
            model=self.config.model,
            messages=messages,
            system=system_prompt,
            **kwargs
        ) as stream:
            for event in stream:
                if event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        yield event.delta.text

    async def _generate_stream_openai(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ):
        """使用OpenAI流式生成文本"""
        client = self.get_async_openai_client()

        # 准备消息
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # 调用流式API
        stream = await client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            stream=True,
            **kwargs
        )

        async for chunk in stream:
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content

    def get_model_info(self) -> Dict[str, Any]:
        """
        获取模型信息

        Returns:
            模型信息字典
        """
        return {
            "provider": self.config.provider,
            "model": self.config.model,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "timeout": self.config.timeout,
            "max_retries": self.config.max_retries,
        }


def init_llm_clients():
    """初始化LLM客户端（供应用启动时调用）"""
    try:
        # 初始化默认客户端
        client = LLMClient.get_default()

        # 测试连接
        logger.info("测试LLM连接...")

        # 根据配置的提供商进行测试
        if client.config.provider == LLMProvider.CLAUDE:
            if not settings.claude_api_key:
                logger.warning("Claude API密钥未配置，Claude功能将不可用")
            else:
                # 简单测试
                test_client = client.get_claude_client()
                logger.info(f"Claude客户端初始化成功，模型: {client.config.model}")

        elif client.config.provider == LLMProvider.OPENAI:
            if not settings.openai_api_key:
                logger.warning("OpenAI API密钥未配置，OpenAI功能将不可用")
            else:
                # 简单测试
                test_client = client.get_openai_client()
                logger.info(f"OpenAI客户端初始化成功，模型: {client.config.model}")

        logger.info("LLM客户端初始化完成")

    except Exception as e:
        logger.error(f"LLM客户端初始化失败: {str(e)}")
        raise