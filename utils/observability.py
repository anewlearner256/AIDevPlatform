"""轻量可观测性组件（指标 + 事件日志）。"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class _MetricsState:
    app_start_time: float = field(default_factory=time.time)
    request_count: int = 0
    request_errors: int = 0
    routes: Dict[str, int] = field(default_factory=dict)
    tenants: Dict[str, int] = field(default_factory=dict)


class ObservabilityManager:
    """进程内指标管理器。"""

    def __init__(self):
        self._state = _MetricsState()
        self._lock = threading.Lock()

    def record_request(self, route: str, tenant_id: str, is_error: bool = False) -> None:
        with self._lock:
            self._state.request_count += 1
            self._state.routes[route] = self._state.routes.get(route, 0) + 1
            self._state.tenants[tenant_id] = self._state.tenants.get(tenant_id, 0) + 1
            if is_error:
                self._state.request_errors += 1

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            uptime = time.time() - self._state.app_start_time
            return {
                "uptime_seconds": round(uptime, 2),
                "request_count": self._state.request_count,
                "request_errors": self._state.request_errors,
                "error_rate": (
                    self._state.request_errors / self._state.request_count
                    if self._state.request_count > 0
                    else 0.0
                ),
                "routes": dict(sorted(self._state.routes.items(), key=lambda x: x[1], reverse=True)),
                "tenants": dict(sorted(self._state.tenants.items(), key=lambda x: x[1], reverse=True)),
            }


observability = ObservabilityManager()
