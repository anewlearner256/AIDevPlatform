"""插件系统。"""

from .plugin_base import PluginBase
from .registry import plugin_registry
from .manager import PluginManager, plugin_manager

__all__ = ["PluginBase", "plugin_registry", "PluginManager", "plugin_manager"]
