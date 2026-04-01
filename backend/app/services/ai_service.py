"""
AI 服务模块
封装对阿里云百炼（兼容 OpenAI 接口）的调用
支持重试机制和超时处理
"""
import asyncio
import json
import re
from typing import List, Dict, Optional
from openai import AsyncOpenAI, APIError, APITimeoutError
from ..config import settings
import logging


logger = logging.getLogger(__name__)
# openai >= 1.51.0, httpx 兼容

# 最大重试次数
MAX_RETRIES = 3
# 重试间隔（秒）
RETRY_DELAY = 1.0


class AIService:
    """AI 对话服务，封装模型调用逻辑"""

    def __init__(self):
        self._client = AsyncOpenAI(
            api_key=settings.ai_api_key,
            base_url=settings.ai_base_url,
            timeout=30.0,
        )
        self.model = settings.ai_model
        logger.info(f"AI 服务初始化完成，模型: {self.model}")

    async def chat(
        self,
        messages: List[Dict],
        system_prompt: str = "",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        发送对话请求，带重试机制
        :param messages: 对话历史（role/content 格式）
        :param system_prompt: 系统提示词
        :param temperature: 温度参数，默认使用配置值
        :param max_tokens: 最大 token 数，默认使用配置值
        :return: AI 回复文本
        """
        request_messages = []
        if system_prompt:
            request_messages.append({"role": "system", "content": system_prompt})
        request_messages.extend(messages)

        for attempt in range(MAX_RETRIES):
            try:
                response = await self._client.chat.completions.create(
                    model=self.model,
                    messages=request_messages,
                    max_tokens=max_tokens or settings.ai_max_tokens,
                    temperature=temperature or settings.ai_temperature,
                )
                reply = response.choices[0].message.content.strip()
                logger.debug(f"AI 回复成功（第 {attempt + 1} 次尝试）")
                return self._filter_output(reply)

            except APITimeoutError:
                logger.warning(f"AI 请求超时（第 {attempt + 1} 次）")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
            except APIError as e:
                logger.error(f"AI API 错误: {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)
            except Exception as e:
                logger.error(f"AI 服务未知错误: {e}")
                break

        # 所有重试失败后的降级回复
        return "抱歉，我现在暂时无法回应，请稍后再试。"

    async def chat_stream(
        self,
        messages: List[Dict],
        system_prompt: str = "",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ):
        """
        流式对话请求，逐块 yield 文本内容
        :param messages: 对话历史（role/content 格式）
        :param system_prompt: 系统提示词
        :param temperature: 温度参数
        :param max_tokens: 最大 token 数
        :yield: 每块文本字符串（delta.content）
        """
        request_messages = []
        if system_prompt:
            request_messages.append({"role": "system", "content": system_prompt})
        request_messages.extend(messages)

        try:
            stream = await self._client.chat.completions.create(
                model=self.model,
                messages=request_messages,
                max_tokens=max_tokens or settings.ai_max_tokens,
                temperature=temperature or settings.ai_temperature,
                stream=True,
            )
            # watchdog 机制：每次迭代获取 chunk 时，如果 45s 内没返回则中断
            while True:
                try:
                    chunk = await asyncio.wait_for(stream.__anext__(), timeout=45.0)
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta and delta.content:
                        yield self._filter_output(delta.content)
                except StopAsyncIteration:
                    break
                except asyncio.TimeoutError:
                    logger.warning("AI 流式请求无响应超时 (watchdog触发)")
                    yield "【系统提示：当前网络波动较大，AI响应超时，已中断连接】"
                    break
        except APITimeoutError:
            logger.warning("AI 流式请求超时")
            yield "抱歉，我现在暂时无法回应，请稍后再试。"
        except APIError as e:
            logger.error(f"AI 流式 API 错误: {e}")
            yield "抱歉，我现在暂时无法回应，请稍后再试。"
        except Exception as e:
            logger.error(f"AI 流式服务未知错误: {e}")
            yield "抱歉，我现在暂时无法回应，请稍后再试。"

    async def extract_key_info(self, conversation_text: str) -> str:
        """
        使用 AI 从对话文本中提取关键信息
        专门用于记忆提取，使用较低温度保证准确性
        :param conversation_text: 对话文本
        :return: JSON 格式的关键信息字符串
        """
        system_prompt = """你是一个专业的用户信息提取助手，任务是从对话中提取用户透露的关键个人信息。

【严格要求】
- 只返回一个 JSON 数组，绝对不要输出任何 JSON 以外的文字、解释或说明
- 如果没有可提取的信息，只返回 []
- 输出格式必须是合法的 JSON 数组

【每条记忆的格式】
{"category": "分类", "content": "具体信息", "importance": 重要性分值}

【分类说明（category 只能是这五种之一）】
- career: 职业规划、工作方向、求职意向、想从事的行业/公司
- goal: 目标、计划、梦想、想学的技术、想发展的方向（如"我想往具身智能发展"）
- personal: 个人背景、专业、学校、技能、家庭情况
- emotion: 情感状态、心理状态、压力焦虑等
- event: 重要经历、已发生的事件

【提取原则】
- 只提取用户（role: user）说的内容，忽略助手的回复
- 重要性(importance)范围 0.1~1.0：职业方向/目标计划 >= 0.8，个人背景 0.6，情感状态 0.5
- 用户明确表达的兴趣方向、想学的技术、想从事的领域 → 必须提取为 goal 或 career 类
- 内容要简洁具体，不超过 80 字

【示例输出】
[
  {"category": "goal", "content": "用户对具身智能（Embodied AI）方向感兴趣，希望往这个方向发展", "importance": 0.9},
  {"category": "personal", "content": "用户目前是在校学生，专业与 AI 相关", "importance": 0.6}
]"""

        messages = [{"role": "user", "content": f"请提取以下对话内容中的关键用户信息：\n\n{conversation_text}"}]

        import re as _re  # 已在顶部全局导入，此行仅为兼容旧引用
        for attempt in range(3):  # 提取最多重试3次
            try:
                response = await self._client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "system", "content": system_prompt}] + messages,
                    max_tokens=800,
                    temperature=0.1,  # 极低温度，强制格式化输出
                )
                raw = response.choices[0].message.content.strip()

                # 先尝试直接解析
                try:
                    json.loads(raw)
                    return raw
                except json.JSONDecodeError:
                    pass

                # 兜底：用 regex 从回复中提取 JSON 数组部分
                match = _re.search(r'\[.*?\]', raw, _re.DOTALL)
                if match:
                    candidate = match.group(0)
                    try:
                        json.loads(candidate)
                        logger.info(f"记忆提取：通过 regex 兜底解析成功")
                        return candidate
                    except json.JSONDecodeError:
                        pass

                logger.warning(f"记忆提取第 {attempt + 1} 次：AI 未返回有效 JSON，原始内容: {raw[:100]}")
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"记忆提取 AI 调用失败（第 {attempt + 1} 次）: {e}")
                await asyncio.sleep(1.0)

        return "[]"
        
    def _filter_output(self, text: str) -> str:
        """
        后置内容过滤：简单剔除极端的违禁词或危险引导
        """
        # 实际项目中可接入更完善的违禁词库或阿里云绿网
        blacklist = [r"自杀方式", r"怎么自杀", r"弄死", r"砍人", r"造反", r"炸弹做法"]
        filtered_text = text
        for pattern in blacklist:
            filtered_text = re.sub(pattern, "***", filtered_text)
        return filtered_text

    async def summarize_history(self, history_text: str) -> str:
        """
        调用 AI 将长对话历史压缩为精简摘要
        """
        if not history_text.strip():
            return ""
            
        system_prompt = (
            "你是一个记忆整理助手。请将以下用户与数字人的历史对话内容压缩成一段精简的摘要(200字以内)。"
            "要提炼出讨论过的主要话题、得出的结论、用户的核心情绪和未解决的问题。不要保留寒暄废话。"
        )
        messages = [{"role": "user", "content": f"【历史对话记录】\n{history_text}"}]
        
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system_prompt}] + messages,
                max_tokens=300,
                temperature=0.2,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"对话历史摘要失败: {e}")
            return ""