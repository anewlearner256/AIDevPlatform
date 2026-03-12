"""智能体基类

定义所有智能体的通用接口和功能。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import asyncio
import loguru
from tenacity import retry, stop_after_attempt, wait_exponential

from config.agents_config import AgentConfig
from utils.llm_client import LLMClient

logger = loguru.logger

class BaseAgent(ABC):
    """智能体基类"""

    def __init__(
        self,
        name: str,
        config: AgentConfig,
        llm_client: Optional[LLMClient] = None
    ):
        """
        初始化智能体

        Args:
            name: 智能体名称
            config: 智能体配置
            llm_client: LLM客户端实例
        """
        self.name = name
        self.config = config
        self.llm_client = llm_client or LLMClient.get_default()

        logger.info(f"初始化智能体: {name}")

    @abstractmethod
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理输入数据并返回结果

        Args:
            input_data: 输入数据字典

        Returns:
            处理结果字典
        """
        pass

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def call_llm(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        调用LLM生成回复

        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            **kwargs: 其他LLM参数

        Returns:
            LLM回复文本
        """
        try:
            # 合并配置参数
            llm_params = {
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
                "timeout": self.config.timeout,
                **kwargs
            }

            # 调用LLM
            response = await self.llm_client.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                **llm_params
            )

            return response

        except Exception as e:
            logger.error(f"智能体 {self.name} LLM调用失败: {str(e)}")
            raise

    async def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """
        验证输入数据

        Args:
            input_data: 输入数据

        Returns:
            是否有效
        """
        # 基本验证：输入是否为字典
        if not isinstance(input_data, dict):
            logger.warning(f"智能体 {self.name} 输入数据不是字典")
            return False

        # 子类可以重写此方法进行更具体的验证
        return True

    async def validate_output(self, output_data: Dict[str, Any]) -> bool:
        """
        验证输出数据

        Args:
            output_data: 输出数据

        Returns:
            是否有效
        """
        # 基本验证：输出是否为字典
        if not isinstance(output_data, dict):
            logger.warning(f"智能体 {self.name} 输出数据不是字典")
            return False

        # 子类可以重写此方法进行更具体的验证
        return True

    async def execute_with_retry(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        带重试的执行方法

        Args:
            input_data: 输入数据

        Returns:
            处理结果
        """
        retries = 0
        max_retries = self.config.max_retries

        while retries <= max_retries:
            try:
                # 验证输入
                if not await self.validate_input(input_data):
                    raise ValueError("输入数据验证失败")

                # 处理数据
                result = await self.process(input_data)

                # 验证输出
                if not await self.validate_output(result):
                    raise ValueError("输出数据验证失败")

                return result

            except Exception as e:
                retries += 1
                logger.warning(
                    f"智能体 {self.name} 执行失败 (重试 {retries}/{max_retries}): {str(e)}"
                )

                if retries > max_retries:
                    logger.error(f"智能体 {self.name} 重试次数耗尽")
                    raise

                # 等待后重试
                await asyncio.sleep(2 ** retries)  # 指数退避

        # 理论上不会执行到这里
        raise RuntimeError("智能体执行失败")

    def get_status(self) -> Dict[str, Any]:
        """
        获取智能体状态

        Returns:
            状态信息字典
        """
        return {
            "name": self.name,
            "enabled": self.config.enabled,
            "max_retries": self.config.max_retries,
            "timeout": self.config.timeout,
        }