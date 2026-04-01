"""
数据库连接模块
使用 motor 异步驱动连接 MongoDB，并在启动时初始化必要索引
"""
import motor.motor_asyncio
from pymongo import ASCENDING, DESCENDING
from .config import settings
import logging

logger = logging.getLogger(__name__)

# 全局数据库连接对象
_client: motor.motor_asyncio.AsyncIOMotorClient = None
_db: motor.motor_asyncio.AsyncIOMotorDatabase = None


async def connect_to_mongo() -> None:
    """启动时连接 MongoDB 并初始化索引"""
    global _client, _db
    try:
        _client = motor.motor_asyncio.AsyncIOMotorClient(
            settings.database_url,
            serverSelectionTimeoutMS=5000,
            maxPoolSize=20,
            minPoolSize=5,
        )
        _db = _client[settings.database_name]

        # 验证连接
        await _db.command("ping")
        logger.info(f"成功连接到 MongoDB: {settings.database_name}")

        # 初始化索引
        await _init_indexes()
    except Exception as e:
        logger.error(f"连接 MongoDB 失败: {e}")
        raise


async def close_mongo_connection() -> None:
    """关闭 MongoDB 连接"""
    global _client
    if _client:
        _client.close()
        logger.info("已关闭 MongoDB 连接")


def get_database() -> motor.motor_asyncio.AsyncIOMotorDatabase:
    """获取数据库实例（用于依赖注入）"""
    if _db is None:
        raise RuntimeError("数据库未初始化，请确保应用已正常启动")
    return _db


async def _init_indexes() -> None:
    """初始化所有集合的索引，提升查询性能（索引已存在时跳过）"""
    db = _db

    # 使用 try/except 避免索引已存在时报错
    try:
        # ── users 集合索引 ──────────────────────────────────────────────────────
        await db["users"].create_index(
            [("username", ASCENDING)], unique=True, name="idx_users_username"
        )
        await db["users"].create_index(
            [("created_at", DESCENDING)], name="idx_users_created_at"
        )

        # ── digital_persons 集合索引 ────────────────────────────────────────────
        await db["digital_persons"].create_index(
            [("user_id", ASCENDING)], name="idx_dp_user_id"
        )
        await db["digital_persons"].create_index(
            [("user_id", ASCENDING), ("created_at", DESCENDING)],
            name="idx_dp_user_created",
        )

        # ── conversations 集合索引 ──────────────────────────────────────────────
        await db["conversations"].create_index(
            [("user_id", ASCENDING), ("updated_at", DESCENDING)],
            name="idx_conv_user_updated",
        )
        await db["conversations"].create_index(
            [("digital_person_id", ASCENDING)], name="idx_conv_dp_id"
        )

        # ── messages 集合索引（独立存储，避免 conversation 文档过大）──────────────
        await db["messages"].create_index(
            [("conversation_id", ASCENDING), ("timestamp", ASCENDING)],
            name="idx_msg_conv_time",
        )

        # ── user_memories 集合索引 ──────────────────────────────────────────────
        await db["user_memories"].create_index(
            [("user_id", ASCENDING), ("digital_person_id", ASCENDING)],
            name="idx_mem_user_dp",
        )
        await db["user_memories"].create_index(
            [("content_hash", ASCENDING)], name="idx_mem_hash"
        )
        await db["user_memories"].create_index(
            [("user_id", ASCENDING), ("category", ASCENDING)],
            name="idx_mem_user_category",
        )

        logger.info("MongoDB 索引初始化完成")
    except Exception as e:
        # 索引已存在或其他非致命错误，记录日志后继续启动
        logger.warning(f"索引初始化时遇到问题（可能已存在，跳过）: {e}")