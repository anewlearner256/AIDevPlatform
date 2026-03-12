"""认证API

处理用户登录、注册、令牌刷新和认证状态。
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import loguru
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config.settings import settings
from models.database import get_async_session, User as UserModel
from api.middleware.auth_middleware import TokenManager
from models.schemas import (
    UserLogin,
    UserRegister,
    UserResponse,
    TokenResponse,
    TokenRefresh,
)

logger = loguru.logger
router = APIRouter()

# 密码哈希
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 认证方案
security = HTTPBearer(auto_error=False)

@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_async_session)
):
    """
    用户登录

    使用用户名和密码获取访问令牌和刷新令牌。
    """
    try:
        # 查找用户
        result = await db.execute(
            select(UserModel).where(UserModel.username == login_data.username)
        )
        user = result.scalar_one_or_none()

        if not user:
            logger.warning(f"登录失败: 用户不存在 - {login_data.username}")
            raise HTTPException(
                status_code=401,
                detail="用户名或密码错误"
            )

        # 验证密码
        if not pwd_context.verify(login_data.password, user.hashed_password):
            logger.warning(f"登录失败: 密码错误 - {login_data.username}")
            raise HTTPException(
                status_code=401,
                detail="用户名或密码错误"
            )

        # 检查用户状态
        if not user.is_active:
            logger.warning(f"登录失败: 用户被禁用 - {login_data.username}")
            raise HTTPException(
                status_code=401,
                detail="用户已被禁用"
            )

        # 创建令牌
        access_token = TokenManager.create_access_token(
            data={"sub": user.id, "username": user.username}
        )

        refresh_token = TokenManager.create_refresh_token(
            data={"sub": user.id}
        )

        logger.info(f"用户登录成功: {user.username}")

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=30 * 60  # 30分钟
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"登录失败: {str(e)}")
        raise HTTPException(status_code=500, detail="登录失败")

@router.post("/register", response_model=UserResponse)
async def register(
    register_data: UserRegister,
    db: AsyncSession = Depends(get_async_session)
):
    """
    用户注册

    创建新用户账户。
    """
    try:
        # 检查用户名是否已存在
        result = await db.execute(
            select(UserModel).where(UserModel.username == register_data.username)
        )
        existing_user = result.scalar_one_or_none()

        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="用户名已存在"
            )

        # 检查邮箱是否已存在
        result = await db.execute(
            select(UserModel).where(UserModel.email == register_data.email)
        )
        existing_email = result.scalar_one_or_none()

        if existing_email:
            raise HTTPException(
                status_code=400,
                detail="邮箱已存在"
            )

        # 创建用户
        hashed_password = pwd_context.hash(register_data.password)
        user = UserModel(
            username=register_data.username,
            email=register_data.email,
            full_name=register_data.full_name,
            hashed_password=hashed_password,
            is_active=True,
            is_superuser=False
        )

        db.add(user)
        await db.commit()
        await db.refresh(user)

        logger.info(f"用户注册成功: {user.username}")

        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            created_at=user.created_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"注册失败: {str(e)}")
        raise HTTPException(status_code=500, detail="注册失败")

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_data: TokenRefresh
):
    """
    刷新访问令牌

    使用刷新令牌获取新的访问令牌。
    """
    try:
        # 验证刷新令牌
        user_id = TokenManager.verify_refresh_token(refresh_data.refresh_token)
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="无效的刷新令牌"
            )

        # 获取用户信息
        async with get_async_session()() as db:
            result = await db.execute(
                select(UserModel).where(UserModel.id == user_id)
            )
            user = result.scalar_one_or_none()

            if not user or not user.is_active:
                raise HTTPException(
                    status_code=401,
                    detail="用户不存在或已被禁用"
                )

        # 创建新的访问令牌
        access_token = TokenManager.create_access_token(
            data={"sub": user.id, "username": user.username}
        )

        # 可以创建新的刷新令牌（可选）
        new_refresh_token = TokenManager.create_refresh_token(
            data={"sub": user.id}
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=30 * 60
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"刷新令牌失败: {str(e)}")
        raise HTTPException(status_code=500, detail="刷新令牌失败")

@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    用户登出

    注：JWT是无状态的，实际登出需要客户端删除令牌。
    此端点主要用于记录登出事件。
    """
    try:
        # 验证令牌以获取用户信息
        from api.middleware.auth_middleware import AuthMiddleware
        auth_middleware = AuthMiddleware()
        user_id = await auth_middleware._verify_token(credentials.credentials)

        if user_id:
            logger.info(f"用户登出: {user_id}")
            # 实际应用中可以将令牌加入黑名单

        return {"message": "登出成功"}

    except Exception as e:
        logger.error(f"登出失败: {str(e)}")
        raise HTTPException(status_code=500, detail="登出失败")

@router.get("/me", response_model=UserResponse)
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    获取当前用户信息
    """
    try:
        # 验证令牌
        from api.middleware.auth_middleware import AuthMiddleware
        auth_middleware = AuthMiddleware()
        user_id = await auth_middleware._verify_token(credentials.credentials)

        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="无效的令牌"
            )

        # 获取用户信息
        async with get_async_session()() as db:
            result = await db.execute(
                select(UserModel).where(UserModel.id == user_id)
            )
            user = result.scalar_one_or_none()

            if not user or not user.is_active:
                raise HTTPException(
                    status_code=401,
                    detail="用户不存在或已被禁用"
                )

            return UserResponse(
                id=user.id,
                username=user.username,
                email=user.email,
                full_name=user.full_name,
                is_active=user.is_active,
                is_superuser=user.is_superuser,
                created_at=user.created_at
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取用户信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取用户信息失败")

@router.get("/health")
async def auth_health():
    """认证服务健康检查"""
    return {"status": "healthy", "service": "auth"}