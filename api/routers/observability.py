"""可观测性与监控路由。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from utils.observability import observability

router = APIRouter()


@router.get("/metrics/system")
async def system_metrics(request: Request) -> Dict[str, Any]:
    data = observability.snapshot()
    data.update(
        {
            "now": datetime.utcnow().isoformat() + "Z",
            "request_id": getattr(request.state, "request_id", None),
            "tenant_id": getattr(request.state, "tenant_id", "default"),
        }
    )
    return data


@router.get("/metrics/health")
async def health_metrics() -> Dict[str, Any]:
    snap = observability.snapshot()
    return {
        "status": "healthy" if snap["error_rate"] < 0.3 else "degraded",
        "request_count": snap["request_count"],
        "error_rate": snap["error_rate"],
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/dashboard", include_in_schema=False)
async def dashboard() -> FileResponse:
    dashboard_file = Path(__file__).resolve().parents[1] / "static" / "dashboard.html"
    return FileResponse(path=str(dashboard_file), media_type="text/html")
