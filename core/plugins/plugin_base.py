"""插件系统基础抽象。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any


class PluginBase(ABC):
    name: str = "base"
    version: str = "0.0.1"

    @abstractmethod
    async def initialize(self) -> None:
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        ...

    @abstractmethod
    async def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        ...
