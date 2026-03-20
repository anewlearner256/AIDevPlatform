"""插件管理器。"""

from __future__ import annotations

from typing import Dict, Any

try:
    import loguru
    logger = loguru.logger
except Exception:  # noqa: BLE001
    import logging
    logger = logging.getLogger(__name__)

from .plugin_base import PluginBase
from .registry import plugin_registry



class HeartbeatPlugin(PluginBase):
    name = "heartbeat"
    version = "1.0.0"

    async def initialize(self) -> None:
        logger.info("HeartbeatPlugin initialized")

    async def shutdown(self) -> None:
        logger.info("HeartbeatPlugin shutdown")

    async def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"plugin": self.name, "status": "ok", "echo": payload}


plugin_registry.register(HeartbeatPlugin)


class PluginManager:
    def __init__(self):
        self.instances: Dict[str, PluginBase] = {}

    async def initialize(self):
        for name in plugin_registry.list_plugins():
            cls = plugin_registry.get(name)
            if cls is None:
                continue
            instance = cls()
            await instance.initialize()
            self.instances[name] = instance
        logger.info(f"Loaded plugins: {list(self.instances.keys())}")

    async def shutdown(self):
        for instance in self.instances.values():
            await instance.shutdown()

    async def execute(self, name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if name not in self.instances:
            raise ValueError(f"Plugin not found: {name}")
        return await self.instances[name].execute(payload)


plugin_manager = PluginManager()
