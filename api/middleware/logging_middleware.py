"""日志中间件

记录HTTP请求和响应日志。
"""

import time
from typing import Callable
from fastapi import Request, Response
import loguru

logger = loguru.logger

async def logging_middleware(
    request: Request,
    call_next: Callable
) -> Response:
    """日志中间件"""

    # 记录请求开始
    start_time = time.time()

    # 获取请求信息
    method = request.method
    url = str(request.url)
    client_ip = request.client.host if request.client else "unknown"

    # 跳过健康检查的详细日志
    if url.endswith("/health") or url.endswith("/"):
        response = await call_next(request)
        return response

    # 记录请求信息
    logger.info(f"请求开始: {method} {url} from {client_ip}")

    try:
        # 处理请求
        response = await call_next(request)

        # 计算处理时间
        process_time = time.time() - start_time

        # 记录响应信息
        logger.info(
            f"请求完成: {method} {url} - "
            f"状态: {response.status_code} - "
            f"耗时: {process_time:.3f}s"
        )

        return response

    except Exception as e:
        # 计算错误处理时间
        process_time = time.time() - start_time

        # 记录错误信息
        logger.error(
            f"请求错误: {method} {url} - "
            f"错误: {str(e)} - "
            f"耗时: {process_time:.3f}s"
        )

        # 重新抛出异常，让错误处理器处理
        raise