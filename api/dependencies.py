"""API依赖项

依赖注入配置，用于FastAPI路由。
"""

from typing import AsyncGenerator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import loguru

from models.database import get_async_session, AsyncSession
from services.knowledge_service import KnowledgeService
from services.requirement_service import RequirementService
from services.project_service import ProjectService
from services.task_service import TaskService
from services.execution_service import ExecutionService
from services.agent_service import AgentService
from utils.llm_client import LLMClient

logger = loguru.logger

# 认证方案（简化版本，实际项目应使用JWT等）
security = HTTPBearer(auto_error=False)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话"""
    async_session = get_async_session()
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """获取当前用户（简化版本）"""
    # 实际项目中应验证JWT令牌
    if credentials is None:
        # 允许匿名访问（开发环境）
        return {"id": "anonymous", "username": "anonymous", "is_superuser": False}

    # 简化验证
    token = credentials.credentials
    # 这里应该验证令牌，这里简化处理
    return {"id": "user_123", "username": "test_user", "is_superuser": True}

async def get_knowledge_service() -> KnowledgeService:
    """获取知识库服务"""
    return KnowledgeService()

async def get_requirement_service() -> RequirementService:
    """获取需求服务"""
    return RequirementService()

async def get_project_service() -> ProjectService:
    """获取项目服务"""
    return ProjectService()

async def get_task_service() -> TaskService:
    """获取任务服务"""
    return TaskService()

async def get_execution_service() -> ExecutionService:
    """获取执行服务"""
    return ExecutionService()

async def get_agent_service() -> AgentService:
    """获取智能体服务"""
    return AgentService()

async def get_llm_client() -> LLMClient:
    """获取LLM客户端"""
    return LLMClient.get_default()

# 权限检查依赖项
def require_admin(user: dict = Depends(get_current_user)):
    """要求管理员权限"""
    if not user.get("is_superuser", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return user

def require_authenticated(user: dict = Depends(get_current_user)):
    """要求已认证用户"""
    if user.get("id") == "anonymous":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要登录"
        )
    return user

# 项目权限检查
async def require_project_member(
    project_id: str,
    user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service)
):
    """要求项目成员权限"""
    # 管理员可以访问所有项目
    if user.get("is_superuser", False):
        return user

    # 检查用户是否是项目成员
    # 这里简化处理，实际项目中应查询数据库
    is_member = await project_service.is_user_project_member(
        project_id=project_id,
        user_id=user["id"]
    )

    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="不是项目成员"
        )

    return user

async def require_project_owner(
    project_id: str,
    user: dict = Depends(get_current_user),
    project_service: ProjectService = Depends(get_project_service)
):
    """要求项目所有者权限"""
    # 管理员可以访问所有项目
    if user.get("is_superuser", False):
        return user

    # 检查用户是否是项目所有者
    is_owner = await project_service.is_user_project_owner(
        project_id=project_id,
        user_id=user["id"]
    )

    if not is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="不是项目所有者"
        )

    return user

# 速率限制依赖项（简化版本）
class RateLimiter:
    """速率限制器"""
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        # 实际项目中应使用Redis等分布式缓存
        self.request_counts = {}

    async def __call__(self, user: dict = Depends(get_current_user)):
        user_id = user["id"]
        current_minute = "current_minute"  # 实际项目中应使用实际分钟

        # 初始化计数器
        if user_id not in self.request_counts:
            self.request_counts[user_id] = {}

        if current_minute not in self.request_counts[user_id]:
            self.request_counts[user_id][current_minute] = 0

        # 检查限制
        if self.request_counts[user_id][current_minute] >= self.requests_per_minute:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="请求过于频繁"
            )

        # 增加计数
        self.request_counts[user_id][current_minute] += 1

        return user

# 创建速率限制器实例
default_rate_limiter = RateLimiter(requests_per_minute=60)
strict_rate_limiter = RateLimiter(requests_per_minute=10)

# 导出依赖项
__all__ = [
    "get_db",
    "get_current_user",
    "get_knowledge_service",
    "get_requirement_service",
    "get_project_service",
    "get_task_service",
    "get_execution_service",
    "get_agent_service",
    "get_llm_client",
    "require_admin",
    "require_authenticated",
    "require_project_member",
    "require_project_owner",
    "default_rate_limiter",
    "strict_rate_limiter",
    "get_current_tenant",
]

async def get_current_tenant(user: dict = Depends(get_current_user)) -> str:
    """获取当前租户ID（从认证信息或默认值推导）。"""
    tenant_id = user.get("tenant_id") if isinstance(user, dict) else None
    return tenant_id or "public"
