"""日志配置"""

import sys
import json
from pathlib import Path
from typing import Dict, Any
import loguru
from loguru import logger

from config.settings import settings

def setup_logging():
    """配置日志系统"""

    # 移除默认处理器
    logger.remove()

    # 日志格式
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    # 控制台日志
    logger.add(
        sys.stderr,
        format=log_format,
        level=settings.log_level.upper(),
        colorize=True,
        backtrace=True,
        diagnose=True,
    )

    # 文件日志（仅在生产环境）
    if settings.is_production:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        # 错误日志
        logger.add(
            log_dir / "error.log",
            format=log_format,
            level="ERROR",
            rotation="10 MB",
            retention="30 days",
            compression="zip",
            backtrace=True,
            diagnose=True,
        )

        # 所有日志
        logger.add(
            log_dir / "app.log",
            format=log_format,
            level="INFO",
            rotation="50 MB",
            retention="7 days",
            compression="zip",
            backtrace=False,
            diagnose=False,
        )

    # 结构化日志（JSON格式，用于日志聚合）
    if settings.is_production:
        def json_formatter(record: Dict[str, Any]) -> str:
            """JSON格式日志格式化器"""
            log_entry = {
                "timestamp": record["time"].isoformat(),
                "level": record["level"].name,
                "message": record["message"],
                "module": record["name"],
                "function": record["function"],
                "line": record["line"],
                "env": settings.app_env,
            }

            # 添加额外字段
            if record.get("extra"):
                log_entry.update(record["extra"])

            # 添加异常信息
            if record.get("exception"):
                log_entry["exception"] = {
                    "type": type(record["exception"]).__name__,
                    "message": str(record["exception"]),
                    "traceback": record["exception"].__traceback__,
                }

            return json.dumps(log_entry)

        logger.add(
            log_dir / "json.log",
            format=json_formatter,
            level="INFO",
            rotation="50 MB",
            retention="7 days",
            compression="zip",
            serialize=True,  # 启用序列化
        )

    logger.info(f"日志系统初始化完成，环境: {settings.app_env}，日志级别: {settings.log_level}")


# 自定义日志级别
def setup_custom_log_levels():
    """设置自定义日志级别"""
    # 添加TRACE级别
    loguru.logger.level("TRACE", color="<cyan>", no=5)

    # 添加SUCCESS级别
    loguru.logger.level("SUCCESS", color="<green><bold>", no=25)

    # 添加AUDIT级别（用于审计日志）
    loguru.logger.level("AUDIT", color="<magenta>", no=35)


# 审计日志装饰器
def audit_log(action: str, resource: str, **kwargs):
    """审计日志装饰器"""
    def decorator(func):
        async def wrapper(*args, **kw):
            try:
                result = await func(*args, **kw)
                logger.bind(
                    audit_action=action,
                    audit_resource=resource,
                    audit_status="success",
                    **kwargs
                ).log("AUDIT", f"{action} {resource} 成功")
                return result
            except Exception as e:
                logger.bind(
                    audit_action=action,
                    audit_resource=resource,
                    audit_status="failed",
                    audit_error=str(e),
                    **kwargs
                ).log("AUDIT", f"{action} {resource} 失败: {str(e)}")
                raise
        return wrapper
    return decorator


# 性能日志装饰器
def performance_log(func_name: str = None):
    """性能日志装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            import time
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time

                logger.bind(
                    perf_function=func_name or func.__name__,
                    perf_execution_time=execution_time,
                    perf_status="success",
                ).log("INFO", f"函数 {func_name or func.__name__} 执行时间: {execution_time:.3f}s")

                return result

            except Exception as e:
                execution_time = time.time() - start_time

                logger.bind(
                    perf_function=func_name or func.__name__,
                    perf_execution_time=execution_time,
                    perf_status="failed",
                    perf_error=str(e),
                ).log("ERROR", f"函数 {func_name or func.__name__} 执行失败，耗时: {execution_time:.3f}s")

                raise

        return wrapper
    return decorator


# 导出
__all__ = [
    "setup_logging",
    "setup_custom_log_levels",
    "audit_log",
    "performance_log",
    "logger",
]