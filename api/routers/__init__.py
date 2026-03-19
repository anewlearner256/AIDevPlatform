"""API路由模块"""

from .requirements import router as requirements_router
from .tasks import router as tasks_router
from .projects import router as projects_router
from .executions import router as executions_router
from .auth import router as auth_router
from .observability import router as observability_router
from .plugins import router as plugins_router

__all__ = [
    "requirements_router",
    "tasks_router",
    "projects_router",
    "executions_router",
    "auth_router",
    "observability_router",
    "plugins_router",
]