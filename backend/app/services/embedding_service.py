"""
向量嵌入服务模块
使用阿里云 Dashscope text-embedding-v3 将文本转换为向量
与现有 AI 服务使用同一个 API Key，无需额外配置
"""
import logging
import asyncio
from typing import List, Optional
import httpx
from ..config import settings

logger = logging.getLogger(__name__)

# Dashscope Embedding API 地址（非 OpenAI 兼容路径，需直接调用）
EMBEDDING_API_URL = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"
EMBEDDING_MODEL = "text-embedding-v3"
EMBEDDING_DIM = 1024  # text-embedding-v3 默认维度


class EmbeddingService:
    """
    向量嵌入服务
    将文本转换为高维向量，用于语义相似度计算（记忆检索等场景）
    """

    def __init__(self):
        self._api_key = settings.ai_api_key
        self._client = httpx.AsyncClient(timeout=15.0)
        logger.info(f"EmbeddingService 初始化完成，模型: {EMBEDDING_MODEL}")

    async def embed_text(self, text: str) -> Optional[List[float]]:
        """
        将单条文本转换为向量
        :param text: 输入文本（建议不超过 512 个 token）
        :return: 浮点数向量列表，失败时返回 None
        """
        result = await self.embed_batch([text])
        return result[0] if result else None

    async def embed_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        批量将文本转换为向量（每批最多 25 条）
        :param texts: 文本列表
        :return: 向量列表（与输入一一对应，失败的位置返回 None）
        """
        if not texts:
            return []

        # Dashscope 单批次最多 25 条
        MAX_BATCH = 25
        results: List[Optional[List[float]]] = [None] * len(texts)

        for i in range(0, len(texts), MAX_BATCH):
            batch = texts[i:i + MAX_BATCH]
            batch_vectors = await self._call_api(batch)
            for j, vec in enumerate(batch_vectors):
                results[i + j] = vec

        return results

    async def _call_api(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        调用 Dashscope Embedding API
        """
        payload = {
            "model": EMBEDDING_MODEL,
            "input": {
                "texts": texts
            },
            "parameters": {
                "dimension": EMBEDDING_DIM
            }
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        for attempt in range(3):
            try:
                resp = await self._client.post(
                    EMBEDDING_API_URL,
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()

                # 解析响应，按 index 排序确保顺序正确
                embeddings_raw = data.get("output", {}).get("embeddings", [])
                sorted_embeddings = sorted(embeddings_raw, key=lambda x: x.get("text_index", 0))
                return [item["embedding"] for item in sorted_embeddings]

            except httpx.HTTPStatusError as e:
                logger.error(f"Embedding API HTTP 错误（第{attempt+1}次）: {e.response.status_code} - {e.response.text}")
                if attempt < 2:
                    await asyncio.sleep(1.0 * (attempt + 1))
            except Exception as e:
                logger.error(f"Embedding API 调用失败（第{attempt+1}次）: {e}")
                if attempt < 2:
                    await asyncio.sleep(1.0)

        # 全部重试失败，返回 None 列表
        return [None] * len(texts)

    @staticmethod
    def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        """
        计算两个向量的余弦相似度
        :return: 相似度值 [-1, 1]，越接近 1 越相似
        """
        if not vec_a or not vec_b:
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = sum(a * a for a in vec_a) ** 0.5
        norm_b = sum(b * b for b in vec_b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    async def close(self):
        """关闭 HTTP 客户端"""
        await self._client.aclose()
