"""智能体工厂

创建和管理智能体实例。
"""

from typing import Dict, Any, Optional, Type
import loguru

from .base_agent import BaseAgent
from .requirement_agent import RequirementAgent
from .task_planner import TaskPlannerAgent
from .development_agent import DevelopmentAgent
from .review_agent import ReviewAgent
from .test_agent import TestAgent
from config.agents_config import AGENTS_CONFIG
from utils.llm_client import LLMClient

logger = loguru.logger


class AgentFactory:
    """智能体工厂"""

    _agents_cache: Dict[str, BaseAgent] = {}
    _llm_client: Optional[LLMClient] = None

    @classmethod
    def set_llm_client(cls, llm_client: LLMClient):
        """设置LLM客户端"""
        cls._llm_client = llm_client

    @classmethod
    def get_llm_client(cls) -> LLMClient:
        """获取LLM客户端"""
        if cls._llm_client is None:
            from utils.llm_client import LLMClient
            cls._llm_client = LLMClient.get_default()
        return cls._llm_client

    @classmethod
    def create_agent(cls, agent_type: str, name: Optional[str] = None) -> BaseAgent:
        """
        创建智能体实例

        Args:
            agent_type: 智能体类型
            name: 智能体名称（可选）

        Returns:
            智能体实例
        """
        # 检查缓存
        cache_key = f"{agent_type}:{name}" if name else agent_type
        if cache_key in cls._agents_cache:
            return cls._agents_cache[cache_key]

        # 获取配置
        if agent_type not in AGENTS_CONFIG:
            raise ValueError(f"未知的智能体类型: {agent_type}")

        config = AGENTS_CONFIG[agent_type]
        llm_client = cls.get_llm_client()
        agent_name = name or f"{agent_type}_agent"

        # 创建智能体实例
        agent_class = cls._get_agent_class(agent_type)
        agent = agent_class(
            name=agent_name,
            config=config,
            llm_client=llm_client
        )

        # 缓存智能体
        cls._agents_cache[cache_key] = agent

        logger.debug(f"创建智能体: {agent_type} ({agent_name})")
        return agent

    @classmethod
    def _get_agent_class(cls, agent_type: str) -> Type[BaseAgent]:
        """获取智能体类"""
        agent_classes = {
            "requirement": RequirementAgent,
            "task_planner": TaskPlannerAgent,
            "development": DevelopmentAgent,
            "review": ReviewAgent,
            "test": TestAgent,
        }

        if agent_type not in agent_classes:
            raise ValueError(f"未实现的智能体类型: {agent_type}")

        return agent_classes[agent_type]

    @classmethod
    def get_agent(cls, agent_type: str, name: Optional[str] = None) -> BaseAgent:
        """
        获取智能体实例（创建或从缓存获取）

        Args:
            agent_type: 智能体类型
            name: 智能体名称（可选）

        Returns:
            智能体实例
        """
        cache_key = f"{agent_type}:{name}" if name else agent_type
        if cache_key in cls._agents_cache:
            return cls._agents_cache[cache_key]

        return cls.create_agent(agent_type, name)

    @classmethod
    def clear_cache(cls, agent_type: Optional[str] = None):
        """
        清空缓存

        Args:
            agent_type: 智能体类型，如果为None则清空所有缓存
        """
        if agent_type:
            # 清除特定类型的缓存
            keys_to_remove = [key for key in cls._agents_cache.keys() if key.startswith(agent_type)]
            for key in keys_to_remove:
                del cls._agents_cache[key]
            logger.debug(f"清除智能体缓存: {agent_type}")
        else:
            # 清除所有缓存
            cls._agents_cache.clear()
            logger.debug("清除所有智能体缓存")

    @classmethod
    def get_available_agent_types(cls) -> list[str]:
        """
        获取可用的智能体类型

        Returns:
            智能体类型列表
        """
        return list(AGENTS_CONFIG.keys())

    @classmethod
    def get_agent_status(cls) -> Dict[str, Any]:
        """
        获取所有智能体状态

        Returns:
            智能体状态信息
        """
        status = {
            "cached_agents": len(cls._agents_cache),
            "available_types": cls.get_available_agent_types(),
            "llm_client_configured": cls._llm_client is not None,
        }

        # 添加缓存中每个智能体的状态
        agent_status = {}
        for cache_key, agent in cls._agents_cache.items():
            agent_status[cache_key] = {
                "name": agent.name,
                "enabled": agent.config.enabled,
                "max_retries": agent.config.max_retries,
            }

        status["agents"] = agent_status
        return status