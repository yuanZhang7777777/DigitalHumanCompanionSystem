"""
FastAPI 依赖注入模块
提供 get_current_user 等通用依赖，供路由函数注入使用
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from bson import ObjectId
from .security import decode_access_token
from ..database import get_database
import logging

logger = logging.getLogger(__name__)

# Bearer Token 提取器
bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db=Depends(get_database),
) -> dict:
    """
    从 Authorization: Bearer <token> 中解析并验证当前用户
    验证失败抛出 401 异常
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="认证失败，请重新登录",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 解码 token
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise credentials_exception

    user_id: str = payload.get("sub")
    if not user_id or not ObjectId.is_valid(user_id):
        raise credentials_exception

    # 查询用户是否存在
    user = await db["users"].find_one({"_id": ObjectId(user_id)})
    if user is None:
        raise credentials_exception

    # 返回用户字典（附加字符串 id）
    user["id"] = str(user["_id"])
    return user
