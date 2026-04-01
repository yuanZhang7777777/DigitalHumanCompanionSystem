"""
认证路由模块
提供用户注册、登录、获取当前用户信息接口
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from bson import ObjectId
from datetime import datetime, timezone

from ..database import get_database
from ..core.security import hash_password, verify_password, create_access_token
from ..core.dependencies import get_current_user
from ..utils.response import success_response, error_response
from ..utils.helpers import get_current_time, serialize_doc
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["认证"])


# ── 请求/响应模型 ────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=20, description="用户名（2-20字符）")
    email: str = Field(..., description="邮箱")
    password: str = Field(..., min_length=6, max_length=50, description="密码（6-50字符）")
    nickname: str = Field(..., min_length=1, max_length=20, description="昵称")


class LoginRequest(BaseModel):
    email: str = Field(..., description="邮箱")
    password: str = Field(..., description="密码")


# ── 路由处理 ─────────────────────────────────────────────────────────────────

@router.post("/register", summary="用户注册")
async def register(body: RegisterRequest, db=Depends(get_database)):
    """
    注册新用户
    - 检查用户名唯一性
    - 对密码进行 bcrypt 哈希
    - 返回 JWT access token
    """
    # 检查用户名或邮箱是否已存在
    existing_username = await db["users"].find_one({"username": body.username})
    if existing_username:
        return error_response("用户名已被占用，请换一个", status_code=409)

    existing_email = await db["users"].find_one({"email": body.email})
    if existing_email:
        return error_response("邮箱已被注册，请直接登录", status_code=409)

    now = get_current_time()
    user_doc = {
        "username": body.username,
        "email": body.email,
        "password_hash": hash_password(body.password),
        "nickname": body.nickname,
        "created_at": now,
        "last_login": now,
    }

    result = await db["users"].insert_one(user_doc)
    user_id = str(result.inserted_id)

    # 生成 JWT token
    token = create_access_token({"sub": user_id})

    logger.info(f"=== [数据变更] 新用户注册 ===")
    logger.info(f"注册用户名: {body.username}")
    logger.info(f"分配的用户 ID: {user_id}")
    logger.info(f"邮箱地址: {body.email}")
    logger.info(f"===============================")

    return success_response(
        data={
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user_id,
                "username": body.username,
                "nickname": body.nickname,
            },
        },
        message="注册成功",
        status_code=201,
    )


@router.post("/login", summary="用户登录")
async def login(body: LoginRequest, db=Depends(get_database)):
    """
    用户登录
    - 验证用户名和密码
    - 更新最后登录时间
    - 返回 JWT access token
    """
    user = await db["users"].find_one({"email": body.email})
    if not user or not verify_password(body.password, user["password_hash"]):
        return error_response("邮箱或密码错误", status_code=401)

    user_id = str(user["_id"])

    # 更新最后登录时间
    await db["users"].update_one(
        {"_id": user["_id"]},
        {"$set": {"last_login": get_current_time()}},
    )

    token = create_access_token({"sub": user_id})

    logger.info(f"=== [数据变更] 用户登录 ===")
    logger.info(f"登录用户: {user['username']} ({user_id})")
    logger.info(f"===========================")

    return success_response(
        data={
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user_id,
                "username": user["username"],
                "nickname": user.get("nickname", user["username"]),
            },
        },
        message="登录成功",
    )


@router.get("/me", summary="获取当前用户信息")
async def get_me(current_user: dict = Depends(get_current_user)):
    """获取当前登录用户的基本信息（需要 Bearer token）"""
    return success_response(
        data={
            "id": current_user["id"],
            "username": current_user["username"],
            "nickname": current_user.get("nickname", current_user["username"]),
            "created_at": current_user["created_at"].isoformat()
            if isinstance(current_user.get("created_at"), datetime)
            else current_user.get("created_at"),
        }
    )