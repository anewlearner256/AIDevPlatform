"""API路由模块"""

from .requirements import router as requirements_router
from .tasks import router as tasks_router
from .projects import router as projects_router
from .executions import router as executions_router

__all__ = [
    "requirements_router",
    "tasks_router",
    "projects_router",
    "executions_router",
]