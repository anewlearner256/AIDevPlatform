"""智能体服务层。"""

from __future__ import annotations

import time
from typing import Dict, Any, Optional, List

import loguru

from core.agents.agent_orchestrator import get_agent_orchestrator
from models.schemas import AgentRequest, AgentResponse

logger = loguru.logger


class AgentService:
    """封装智能体编排器的服务接口。"""

    async def execute_agent(self, request: AgentRequest) -> AgentResponse:
        start = time.perf_counter()
        orchestrator = await get_agent_orchestrator()

        output = await orchestrator.execute_agent(
            agent_type=request.agent_type,
            input_data=request.input_data,
            context=request.config_overrides or {},
        )

        elapsed = time.perf_counter() - start
        return AgentResponse(
            agent_type=request.agent_type,
            output_data=output,
            execution_time=elapsed,
            status="completed",
        )

    async def list_available_agents(self) -> List[str]:
        orchestrator = await get_agent_orchestrator()
        return sorted(list(orchestrator.agents.keys()))

    async def get_agent_status(self, agent_type: str) -> Optional[Dict[str, Any]]:
        orchestrator = await get_agent_orchestrator()
        if agent_type not in orchestrator.agents:
            return None
        return orchestrator.agents[agent_type].get_status()
