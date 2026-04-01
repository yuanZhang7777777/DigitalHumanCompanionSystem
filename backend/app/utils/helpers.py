"""
通用工具函数
"""
from datetime import datetime, timezone
from bson import ObjectId
import re
import hashlib


def get_current_time() -> datetime:
    """获取当前 UTC 时间"""
    return datetime.now(timezone.utc)


def validate_object_id(oid: str) -> bool:
    """验证字符串是否为合法的 MongoDB ObjectId"""
    if not oid:
        return False
    return ObjectId.is_valid(str(oid))


def sanitize_input(text: str) -> str:
    """清理用户输入，去除首尾空白，过滤HTML标签，限制长度"""
    if not text:
        return ""
    # 去除首尾空白
    text = text.strip()
    # 过滤HTML标签（防止XSS注入）
    text = re.sub(r'<[^>]+>', '', text)
    # 限制最大长度（2000字符）
    return text[:2000]


def compute_content_hash(content: str) -> str:
    """
    计算内容的 MD5 哈希，用于记忆去重
    对内容进行规范化后再哈希，提高去重准确性
    """
    # 规范化：去除多余空白、转小写
    normalized = re.sub(r"\s+", " ", content.strip().lower())
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


def serialize_doc(doc: dict) -> dict:
    """
    将 MongoDB 文档中的 ObjectId 和 datetime 转换为可序列化的字符串
    """
    if doc is None:
        return None
    result = {}
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            result[key] = str(value)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, dict):
            result[key] = serialize_doc(value)
        elif isinstance(value, list):
            result[key] = [
                serialize_doc(item) if isinstance(item, dict) else
                str(item) if isinstance(item, ObjectId) else
                item.isoformat() if isinstance(item, datetime) else item
                for item in value
            ]
        else:
            result[key] = value
    # 将 _id 映射为 id
    if "_id" in result:
        result["id"] = result.pop("_id")
    return result