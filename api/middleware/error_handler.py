"""错误处理中间件

全局错误处理，将异常转换为标准化的API响应。
"""

import traceback
from typing import Callable
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
import loguru

logger = loguru.logger

async def error_handler(
    request: Request,
    call_next: Callable
) -> Response:
    """错误处理中间件"""

    try:
        return await call_next(request)

    except HTTPException as e:
        # FastAPI HTTP异常
        logger.warning(
            f"HTTP异常: {request.method} {request.url} - "
            f"状态: {e.status_code} - 详情: {e.detail}"
        )
        return JSONResponse(
            status_code=e.status_code,
            content={
                "error": {
                    "code": e.status_code,
                    "message": str(e.detail),
                    "type": "http_exception"
                }
            }
        )

    except Exception as e:
        # 未处理的异常
        logger.error(
            f"未处理异常: {request.method} {request.url} - "
            f"错误: {str(e)}\n"
            f"堆栈跟踪: {traceback.format_exc()}"
        )

        # 生产环境隐藏详细错误信息
        error_message = "内部服务器错误"
        if request.app.debug:
            error_message = f"{type(e).__name__}: {str(e)}"

        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": 500,
                    "message": error_message,
                    "type": "internal_server_error"
                }
            }
        )