"""插件系统API。"""

from __future__ import annotations

from typing import Dict, Any

from fastapi import APIRouter, Body, HTTPException

from core.plugins import plugin_manager

router = APIRouter()


@router.get("/")
async def list_plugins():
    return {"plugins": sorted(plugin_manager.instances.keys())}


@router.post("/{plugin_name}/execute")
async def execute_plugin(plugin_name: str, payload: Dict[str, Any] = Body(default_factory=dict)):
    try:
        result = await plugin_manager.execute(plugin_name, payload)
        return {"plugin": plugin_name, "result": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
