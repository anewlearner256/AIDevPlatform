"""插件注册中心。"""

from __future__ import annotations

from typing import Dict, Type

from .plugin_base import PluginBase


class PluginRegistry:
    def __init__(self):
        self._plugins: Dict[str, Type[PluginBase]] = {}

    def register(self, plugin_cls: Type[PluginBase]) -> None:
        self._plugins[plugin_cls.name] = plugin_cls

    def list_plugins(self):
        return sorted(self._plugins.keys())

    def get(self, name: str):
        return self._plugins.get(name)


plugin_registry = PluginRegistry()
