"""认证和授权中间件

处理JWT令牌验证和用户权限检查。
"""

from typing import Optional, Tuple
from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import loguru
from datetime import datetime, timedelta

from config.settings import settings
from models.database import get_async_session
from models.database import User as UserModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = loguru.logger

# JWT配置
JWT_SECRET_KEY = settings.secret_key
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 30
JWT_REFRESH_TOKEN_EXPIRE_DAYS = 7

# 权限角色
ROLES = {
    "admin": ["admin", "user", "viewer"],
    "user": ["user", "viewer"],
    "viewer": ["viewer"]
}

class AuthMiddleware:
    """认证中间件"""

    def __init__(self):
        self.security = HTTPBearer(auto_error=False)

    async def __call__(self, request: Request):
        """处理请求认证"""
        # 跳过认证的路由
        if await self._should_skip_auth(request):
            return

        # 提取令牌
        credentials = await self._extract_credentials(request)
        if not credentials:
            raise HTTPException(
                status_code=401,
                detail="未提供认证令牌",
                headers={"WWW-Authenticate": "Bearer"}
            )

        # 验证令牌
        user_id = await self._verify_token(credentials.credentials)
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="无效或过期的令牌",
                headers={"WWW-Authenticate": "Bearer"}
            )

        # 获取用户信息
        user = await self._get_user(user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=401,
                detail="用户不存在或已被禁用"
            )

        # 将用户信息添加到请求状态
        request.state.user = user
        request.state.user_id = user_id
        request.state.roles = self._get_user_roles(user)

        logger.info(f"用户认证成功: {user.username} ({user_id})")

    async def _should_skip_auth(self, request: Request) -> bool:
        """检查是否应该跳过认证"""
        skip_paths = [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/refresh",
        ]

        # 检查路径前缀
        path = request.url.path
        if any(path.startswith(skip_path) for skip_path in skip_paths):
            return True

        # 检查HTTP方法（允许OPTIONS预检请求）
        if request.method == "OPTIONS":
            return True

        return False

    async def _extract_credentials(self, request: Request) -> Optional[HTTPAuthorizationCredentials]:
        """提取认证凭据"""
        # 从Authorization头提取
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None

        # 支持Bearer令牌
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        return None

    async def _verify_token(self, token: str) -> Optional[str]:
        """验证JWT令牌"""
        try:
            payload = jwt.decode(
                token,
                JWT_SECRET_KEY,
                algorithms=[JWT_ALGORITHM]
            )
            user_id = payload.get("sub")
            token_type = payload.get("type")

            # 检查令牌类型
            if token_type != "access":
                logger.warning(f"无效的令牌类型: {token_type}")
                return None

            # 检查过期时间
            exp = payload.get("exp")
            if exp and datetime.fromtimestamp(exp) < datetime.utcnow():
                logger.warning("令牌已过期")
                return None

            return user_id

        except JWTError as e:
            logger.error(f"JWT验证失败: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"令牌验证失败: {str(e)}")
            return None

    async def _get_user(self, user_id: str) -> Optional[UserModel]:
        """获取用户信息"""
        try:
            async with get_async_session()() as session:
                result = await session.execute(
                    select(UserModel).where(UserModel.id == user_id)
                )
                user = result.scalar_one_or_none()
                return user
        except Exception as e:
            logger.error(f"获取用户失败: {str(e)}")
            return None

    def _get_user_roles(self, user: UserModel) -> list:
        """获取用户角色"""
        roles = ["viewer"]  # 默认角色

        if user.is_superuser:
            roles.append("admin")

        roles.append("user")

        return roles

    def check_permission(self, user_roles: list, required_role: str) -> bool:
        """检查用户权限"""
        for role in user_roles:
            if required_role in ROLES.get(role, []):
                return True
        return False


# 令牌工具函数
class TokenManager:
    """令牌管理器"""

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """创建访问令牌"""
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })

        encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        return encoded_jwt

    @staticmethod
    def create_refresh_token(data: dict) -> str:
        """创建刷新令牌"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)

        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        })

        encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        return encoded_jwt

    @staticmethod
    def verify_refresh_token(token: str) -> Optional[str]:
        """验证刷新令牌"""
        try:
            payload = jwt.decode(
                token,
                JWT_SECRET_KEY,
                algorithms=[JWT_ALGORITHM]
            )

            if payload.get("type") != "refresh":
                return None

            user_id = payload.get("sub")
            return user_id

        except JWTError:
            return None


# 依赖项
async def get_current_user(request: Request) -> UserModel:
    """获取当前用户依赖项"""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="用户未认证"
        )
    return user

async def get_current_user_id(request: Request) -> str:
    """获取当前用户ID依赖项"""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="用户未认证"
        )
    return user_id

def require_role(required_role: str):
    """角色权限装饰器"""
    def role_checker(request: Request):
        user_roles = getattr(request.state, "roles", [])
        auth_middleware = AuthMiddleware()

        if not auth_middleware.check_permission(user_roles, required_role):
            raise HTTPException(
                status_code=403,
                detail=f"需要 '{required_role}' 角色权限"
            )
    return role_checker

# 全局中间件实例
auth_middleware = AuthMiddleware()