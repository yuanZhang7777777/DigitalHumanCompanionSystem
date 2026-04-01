"""
统一响应格式工具
所有 API 接口使用统一的 JSON 响应结构
"""
from fastapi.responses import JSONResponse
from typing import Any, Optional
from datetime import datetime, timezone


def success_response(
    data: Any = None,
    message: str = "操作成功",
    status_code: int = 200,
) -> JSONResponse:
    """成功响应"""
    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "message": message,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


def error_response(
    message: str = "操作失败",
    status_code: int = 400,
    detail: Optional[str] = None,
) -> JSONResponse:
    """错误响应"""
    content = {
        "success": False,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if detail:
        content["detail"] = detail
    return JSONResponse(status_code=status_code, content=content)