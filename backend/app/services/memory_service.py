"""
记忆提取服务模块
核心功能：从用户聊天历史中提取关键信息，去重后存入 MongoDB
算法设计：
  1. 触发条件：每 N 条消息（可配置）触发一次提取
  2. AI 提取：调用 AI 从对话文本中识别关键信息
  3. 去重算法：基于内容哈希 + 关键词重叠度避免冗余存储
  4. 分类存储：career/emotion/personal/goal/event 五类
  5. 向量化检索：存储时生成 embedding，对话时按语义相关性检索（方案A）
"""
import json
import logging
from typing import List, Dict, Optional
from datetime import datetime, timezone
from bson import ObjectId

from ..config import settings
from ..utils.helpers import compute_content_hash, get_current_time

logger = logging.getLogger(__name__)

# 记忆分类
MEMORY_CATEGORIES = {
    "career": "职业规划",
    "emotion": "情感状态",
    "personal": "个人信息",
    "goal": "目标计划",
    "event": "重要经历",
}


class MemoryService:
    """
    用户记忆提取与管理服务
    负责从对话历史中提取关键信息并去重存储到 MongoDB
    支持向量化语义检索（方案A）
    """

    def __init__(self, ai_service, embedding_service=None):
        self._ai = ai_service
        self._emb = embedding_service  # 向量化服务，可为 None（降级为旧逻辑）

    async def should_extract(self, conversation_id: str, db) -> bool:
        """
        判断是否需要触发记忆提取
        条件：每发送 2 条消息（1轮对话）就触发一次提取
        """
        threshold = max(2, settings.memory_extract_threshold // 3)  # 至少每2条触发
        count = await db["messages"].count_documents(
            {"conversation_id": ObjectId(conversation_id)}
        )
        # 每达到阈值倍数时触发（2、4、6...）
        return count > 0 and count % threshold == 0

    async def extract_and_store(
        self,
        user_id: str,
        digital_person_id: str,
        conversation_id: str,
        messages: List[Dict],
        db,
    ) -> int:
        """
        从对话消息中提取关键信息并存储
        :return: 新存储的记忆条数
        """
        if not messages:
            return 0

        # 只取用户消息构建对话文本（减少 token 消耗）
        user_messages = [
            f"用户: {msg['content']}"
            for msg in messages
            if msg.get("role") == "user" and msg.get("content")
        ]

        if len(user_messages) < 1:
            # 至少要有1条用户消息才提取
            return 0

        conversation_text = "\n".join(user_messages[-20:])  # 最多取最近20条

        # 调用 AI 提取关键信息
        raw_result = await self._ai.extract_key_info(conversation_text)

        # 解析 JSON 结果
        try:
            extracted_items = json.loads(raw_result)
            if not isinstance(extracted_items, list):
                return 0
        except json.JSONDecodeError:
            logger.warning(f"记忆提取 JSON 解析失败: {raw_result[:200]}")
            return 0

        # 过滤无效条目
        valid_items = [
            item for item in extracted_items
            if isinstance(item, dict)
            and item.get("content", "").strip()
            and item.get("category") in MEMORY_CATEGORIES
            and isinstance(item.get("importance", 0), (int, float))
        ]

        if not valid_items:
            return 0

        # 去重存储
        stored_count = await self._deduplicate_and_store(
            user_id=user_id,
            digital_person_id=digital_person_id,
            conversation_id=conversation_id,
            items=valid_items,
            db=db,
        )

        logger.info(
            f"记忆提取完成: 用户={user_id}, 数字人={digital_person_id}, "
            f"提取={len(valid_items)}, 新存储={stored_count}"
        )
        return stored_count

    async def _deduplicate_and_store(
        self,
        user_id: str,
        digital_person_id: str,
        conversation_id: str,
        items: List[Dict],
        db,
    ) -> int:
        """
        去重算法：
        1. 计算内容哈希，精确匹配去重
        2. 关键词重叠度检测（>60% 重叠则视为重复）
        3. 对于重复内容，更新重要性评分（取最大值）
        """
        stored_count = 0
        now = get_current_time()

        # 获取该用户+数字人的现有记忆（用于去重比对）
        existing_memories = []
        async for mem in db["user_memories"].find({
            "user_id": ObjectId(user_id),
            "digital_person_id": ObjectId(digital_person_id),
        }, {"content_hash": 1, "content": 1, "importance_score": 1}):
            existing_memories.append(mem)

        existing_hashes = {mem["content_hash"] for mem in existing_memories}

        for item in items:
            content = item["content"].strip()
            category = item["category"]
            importance = min(1.0, max(0.1, float(item.get("importance", 0.5))))

            # 第一层去重：内容哈希精确匹配
            content_hash = compute_content_hash(content)
            if content_hash in existing_hashes:
                # 已存在相同内容，更新重要性评分（取最大值）
                await db["user_memories"].update_one(
                    {"content_hash": content_hash, "user_id": ObjectId(user_id)},
                    {
                        "$max": {"importance_score": importance},
                        "$set": {"updated_at": now},
                    },
                )
                continue

            # 第二层去重：关键词重叠度检测
            if self._is_semantically_duplicate(content, existing_memories):
                continue

            # 生成向量（如果 EmbeddingService 可用）
            embedding_vector = None
            if self._emb is not None:
                try:
                    embedding_vector = await self._emb.embed_text(content)
                except Exception as e:
                    logger.warning(f"记忆向量化失败（将以无向量方式存储）: {e}")

            # 存储新记忆
            memory_doc = {
                "user_id": ObjectId(user_id),
                "digital_person_id": ObjectId(digital_person_id),
                "source_conversation_id": ObjectId(conversation_id),
                "category": category,
                "content": content,
                "importance_score": importance,
                "content_hash": content_hash,
                "embedding": embedding_vector,  # 向量字段，None 表示未向量化
                "extracted_at": now,
                "updated_at": now,
            }

            await db["user_memories"].insert_one(memory_doc)
            existing_hashes.add(content_hash)
            existing_memories.append({"content_hash": content_hash, "content": content})
            stored_count += 1

        return stored_count

    def _is_semantically_duplicate(
        self, new_content: str, existing_memories: List[Dict]
    ) -> bool:
        """
        基于关键词重叠度的语义去重
        当新内容与现有记忆的关键词重叠度超过阈值时，视为重复
        """
        threshold = settings.memory_similarity_threshold

        new_words = set(new_content.replace("，", " ").replace("。", " ").split())
        if len(new_words) < 3:
            return False  # 内容太短，跳过语义去重

        for existing in existing_memories:
            existing_content = existing.get("content", "")
            existing_words = set(
                existing_content.replace("，", " ").replace("。", " ").split()
            )
            if not existing_words:
                continue

            # 计算 Jaccard 相似度
            intersection = len(new_words & existing_words)
            union = len(new_words | existing_words)
            similarity = intersection / union if union > 0 else 0

            if similarity >= threshold:
                return True

        return False

    async def get_memories(
        self,
        user_id: str,
        digital_person_id: str,
        db,
        limit: int = 50,
    ) -> List[Dict]:
        """
        获取用户对特定数字人的完整记忆列表（用于前端展示）
        按重要性降序排列
        """
        memories = []
        cursor = (
            db["user_memories"]
            .find(
                {
                    "user_id": ObjectId(user_id),
                    "digital_person_id": ObjectId(digital_person_id),
                },
                {"embedding": 0}  # 不返回向量字段，节省带宽
            )
            .sort("importance_score", -1)
            .limit(limit)
        )

        async for mem in cursor:
            memories.append({
                "id": str(mem["_id"]),
                "category": mem.get("category", "personal"),
                "content": mem.get("content", ""),
                "importance_score": mem.get("importance_score", 0.5),
                "extracted_at": mem["extracted_at"].isoformat()
                if isinstance(mem.get("extracted_at"), datetime)
                else mem.get("extracted_at"),
            })

        return memories

    async def get_relevant_memories(
        self,
        user_id: str,
        digital_person_id: str,
        query_text: str,
        db,
        top_k: int = 5,
    ) -> List[Dict]:
        """
        【向量化语义检索】根据当前用户输入，检索最相关的记忆（方案A核心）
        流程：
          1. 将用户输入向量化
          2. 从 MongoDB 取出所有有向量的记忆
          3. 计算余弦相似度，取 top_k 最高分
          4. 若 EmbeddingService 不可用，降级为按重要性排序取 top_k
        :param query_text: 当前用户消息（作为检索 query）
        :param top_k: 返回最相关的记忆条数（默认 5 条）
        :return: 按相关性排序的记忆列表
        """
        # ── 降级模式：无 EmbeddingService 时按重要性取 top_k ──
        if self._emb is None:
            logger.debug("EmbeddingService 不可用，降级为重要性排序")
            return await self._get_memories_by_importance(user_id, digital_person_id, db, top_k)

        # ── 向量化检索 ──
        try:
            # 将查询文本向量化
            query_vec = await self._emb.embed_text(query_text)
            if not query_vec:
                logger.warning("查询向量化失败，降级为重要性排序")
                return await self._get_memories_by_importance(user_id, digital_person_id, db, top_k)

            # 从数据库取所有有 embedding 向量的记忆
            all_memories = []
            cursor = db["user_memories"].find(
                {
                    "user_id": ObjectId(user_id),
                    "digital_person_id": ObjectId(digital_person_id),
                    "embedding": {"$ne": None, "$exists": True},
                }
            )
            async for mem in cursor:
                all_memories.append(mem)

            if not all_memories:
                # 没有任何带向量的记忆，降级
                logger.debug("无带向量的记忆，降级为重要性排序")
                return await self._get_memories_by_importance(user_id, digital_person_id, db, top_k)

            # 计算每条记忆与查询的余弦相似度
            scored = []
            for mem in all_memories:
                mem_vec = mem.get("embedding")
                if not mem_vec:
                    continue

                sim = self._emb.cosine_similarity(query_vec, mem_vec)
                # 综合得分：相似度 * 0.7 + 重要性 * 0.3（兼顾相关性和重要性）
                score = sim * 0.7 + mem.get("importance_score", 0.5) * 0.3
                scored.append((score, mem))

            # 按综合得分降序排列，取 top_k
            scored.sort(key=lambda x: x[0], reverse=True)
            top_memories = scored[:top_k]

            result = []
            for score, mem in top_memories:
                result.append({
                    "id": str(mem["_id"]),
                    "category": mem.get("category", "personal"),
                    "content": mem.get("content", ""),
                    "importance_score": mem.get("importance_score", 0.5),
                    "relevance_score": round(score, 4),  # 附带相关性分数便于调试
                    "extracted_at": mem["extracted_at"].isoformat()
                    if isinstance(mem.get("extracted_at"), datetime)
                    else mem.get("extracted_at"),
                })

            logger.debug(
                f"向量检索完成：查询='{query_text[:30]}...', "
                f"候选={len(all_memories)}, 返回={len(result)}"
            )
            return result

        except Exception as e:
            logger.error(f"向量检索异常，降级为重要性排序: {e}", exc_info=True)
            return await self._get_memories_by_importance(user_id, digital_person_id, db, top_k)

    async def _get_memories_by_importance(
        self,
        user_id: str,
        digital_person_id: str,
        db,
        limit: int = 5,
    ) -> List[Dict]:
        """按重要性排序获取记忆（降级方案）"""
        memories = []
        cursor = (
            db["user_memories"]
            .find(
                {
                    "user_id": ObjectId(user_id),
                    "digital_person_id": ObjectId(digital_person_id),
                },
                {"embedding": 0}
            )
            .sort("importance_score", -1)
            .limit(limit)
        )
        async for mem in cursor:
            memories.append({
                "id": str(mem["_id"]),
                "category": mem.get("category", "personal"),
                "content": mem.get("content", ""),
                "importance_score": mem.get("importance_score", 0.5),
                "extracted_at": mem["extracted_at"].isoformat()
                if isinstance(mem.get("extracted_at"), datetime)
                else mem.get("extracted_at"),
            })
        return memories

    async def delete_memory(self, memory_id: str, user_id: str, db) -> bool:
        """删除指定记忆（验证所有权）"""
        result = await db["user_memories"].delete_one({
            "_id": ObjectId(memory_id),
            "user_id": ObjectId(user_id),
        })
        return result.deleted_count > 0
