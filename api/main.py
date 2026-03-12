"""FastAPI应用入口点"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import loguru

from config.settings import settings
from api.routers import requirements, tasks, projects, executions
from api.middleware import logging_middleware, error_handler

# 配置日志
logger = loguru.logger

def create_app() -> FastAPI:
    """创建FastAPI应用实例"""

    # 应用配置
    app_config = {
        "title": settings.app_name,
        "description": "AI自动开发平台API",
        "version": "0.1.0",
        "docs_url": "/docs" if settings.debug else None,
        "redoc_url": "/redoc" if settings.debug else None,
        "openapi_url": f"{settings.api_prefix}/openapi.json" if settings.debug else None,
    }

    app = FastAPI(**app_config)

    # 添加中间件
    add_middlewares(app)

    # 添加路由
    add_routers(app)

    # 添加生命周期事件
    add_lifespan_events(app)

    logger.info(f"应用启动成功，环境: {settings.app_env}")
    return app


def add_middlewares(app: FastAPI):
    """添加中间件"""

    # CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 信任主机中间件
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"] if settings.debug else ["localhost", "127.0.0.1"],
    )

    # 自定义中间件
    app.middleware("http")(logging_middleware)
    app.middleware("http")(error_handler)

    # 认证中间件
    from api.middleware.auth_middleware import auth_middleware
    app.middleware("http")(auth_middleware)


def add_routers(app: FastAPI):
    """添加路由"""

    # 健康检查端点
    @app.get("/")
    async def root():
        return {"message": "AI自动开发平台API", "version": "0.1.0"}

    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "timestamp": "2026-03-07T15:46:00Z"}

    # API路由
    app.include_router(
        requirements.router,
        prefix=f"{settings.api_prefix}/requirements",
        tags=["需求管理"]
    )

    app.include_router(
        tasks.router,
        prefix=f"{settings.api_prefix}/tasks",
        tags=["任务管理"]
    )

    app.include_router(
        projects.router,
        prefix=f"{settings.api_prefix}/projects",
        tags=["项目管理"]
    )

    app.include_router(
        executions.router,
        prefix=f"{settings.api_prefix}/executions",
        tags=["执行管理"]
    )


def add_lifespan_events(app: FastAPI):
    """添加生命周期事件"""

    @app.on_event("startup")
    async def startup_event():
        """应用启动时执行"""
        logger.info("应用启动中...")

        # 初始化数据库连接池
        from models.database import init_db
        await init_db()

        # 初始化向量数据库
        from core.knowledge_base.vector_store import init_vector_store
        init_vector_store()

        # 初始化LLM客户端
        from utils.llm_client import init_llm_clients
        init_llm_clients()

        logger.info("应用启动完成")

    @app.on_event("shutdown")
    async def shutdown_event():
        """应用关闭时执行"""
        logger.info("应用关闭中...")

        # 清理资源
        from models.database import close_db
        await close_db()

        logger.info("应用关闭完成")


# 创建应用实例
app = create_app()