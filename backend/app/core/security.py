"""
安全核心模块
提供 JWT token 生成/验证 和 密码哈希功能
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from ..config import settings

# 密码哈希上下文（bcrypt 算法）
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── 密码工具 ────────────────────────────────────────────────────────────────

def hash_password(plain_password: str) -> str:
    """对明文密码进行 bcrypt 哈希"""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码与哈希是否匹配"""
    return pwd_context.verify(plain_password, hashed_password)


# ── JWT Token 工具 ──────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    生成 JWT access token
    :param data: 载荷数据（通常包含 sub: user_id）
    :param expires_delta: 过期时间，默认使用配置值
    :return: 编码后的 JWT 字符串
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> Optional[dict]:
    """
    解码并验证 JWT token
    :param token: JWT 字符串
    :return: 载荷字典，验证失败返回 None
    """
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        return payload
    except JWTError:
        return None
