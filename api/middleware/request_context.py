"""请求上下文中间件：注入 request_id 与 tenant_id。"""

from __future__ import annotations

import uuid
from fastapi import Request

from config.settings import settings


async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    tenant_id = request.headers.get("X-Tenant-ID", settings.default_tenant_id)

    request.state.request_id = request_id
    request.state.tenant_id = tenant_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Tenant-ID"] = tenant_id
    return response
