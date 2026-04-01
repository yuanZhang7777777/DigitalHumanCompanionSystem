"""
对话路由模块
提供消息发送（普通版/流式版）、对话查询、对话列表等接口
核心功能：发送消息时同步触发记忆提取（每条消息都触发）
"""
import asyncio
import json
import logging
from typing import Optional, AsyncGenerator
from fastapi import APIRouter, Depends, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from bson import ObjectId
from datetime import datetime

from ..database import get_database
from ..core.dependencies import get_current_user
from ..utils.response import success_response, error_response
from ..utils.helpers import get_current_time, sanitize_input, validate_object_id
from ..services.ai_service import AIService
from ..services.prompt_service import PromptService
from ..services.emotion_service import EmotionService
from ..services.memory_service import MemoryService
from ..services.video_service import VideoService
from ..services.embedding_service import EmbeddingService
from ..services.weather_service import WeatherService
from ..services.interview_service import InterviewService
from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/conversations", tags=["对话"])

# 服务实例（单例）
_ai_service = AIService()
_prompt_service = PromptService()
_emotion_service = EmotionService()
_embedding_service = EmbeddingService()  # 向量嵌入服务（记忆语义检索用）
_memory_service = MemoryService(_ai_service, _embedding_service)  # 注入向量服务
_video_service = VideoService()
_weather_service = WeatherService()
_interview_service = InterviewService()

# ── 用户级并发控制 ────────────────────────────────────────────────────────────
_user_semaphores = {}

def get_user_semaphore(user_id: str):
    if user_id not in _user_semaphores:
        # 默认允许每个用户 2 个并发请求
        max_concurrent = getattr(settings, 'max_concurrent_per_user', 2)
        _user_semaphores[user_id] = asyncio.Semaphore(max_concurrent)
    return _user_semaphores[user_id]


# ── 请求模型 ─────────────────────────────────────────────────────────────────

class SendMessageRequest(BaseModel):
    digital_person_id: str = Field(..., description="数字人 ID")
    message: str = Field(..., min_length=1, max_length=2000, description="用户消息")
    conversation_id: Optional[str] = Field(default=None, description="对话 ID（续接已有对话）")


# ── 后台任务 ─────────────────────────────────────────────────────────────────

async def _trigger_memory_extraction(
    user_id: str,
    digital_person_id: str,
    conversation_id: str,
    db,
):
    """
    后台触发记忆提取任务
    每条消息发送后都执行，只提取最新的用户消息
    """
    try:
        # 获取最近的消息用于提取（每次都触发，取最近 4 条保证上下文）
        messages = []
        cursor = (
            db["messages"]
            .find({"conversation_id": ObjectId(conversation_id)})
            .sort("timestamp", -1)
            .limit(4)
        )
        async for msg in cursor:
            messages.append(msg)
        messages.reverse()  # 恢复时间顺序

        if messages:
            count = await _memory_service.extract_and_store(
                user_id=user_id,
                digital_person_id=digital_person_id,
                conversation_id=conversation_id,
                messages=messages,
                db=db,
            )
            if count > 0:
                logger.info(f"后台记忆提取完成，新增 {count} 条记忆")
    except Exception as e:
        logger.error(f"后台记忆提取失败: {e}", exc_info=True)


# ── 路由处理 ─────────────────────────────────────────────────────────────────

async def _trigger_video_generation(
    user_id: str,
    digital_person_id: str,
    db
):
    """
    后台触发视频生成任务
    检测该数字人是否有上传的头像但没有生成视频，如果有，则启动阿里云视频生成并永久保存。
    """
    import os
    import base64
    import time
    try:
        person = await db["digital_persons"].find_one({"_id": ObjectId(digital_person_id)})
        if not person or not person.get("avatar"):
            return
            
        avatar_url = person["avatar"]
        
        # 核心逻辑改进：如果已经存在视频，且用于生成视频的头像没变，则跳过生成（复用）
        if person.get("speaking_video_url") and person.get("last_avatar_for_video") == avatar_url:
            logger.info(f"数字人 {digital_person_id} 的头像未变，复用已有动态视频。")
            return
            
        local_avatar_path = None
        
        # 处理本地静态路径
        if avatar_url.startswith("/static/"):
            local_avatar_path = os.path.join("app", avatar_url.lstrip("/"))
            
        # 处理 Base64 编码的图片
        elif avatar_url.startswith("data:image"):
            # 提取 base64 数据部分
            try:
                header, encoded = avatar_url.split(",", 1)
                img_data = base64.b64decode(encoded)
                # 临时文件路径
                os.makedirs(os.path.join("app", "static", "avatars"), exist_ok=True)
                temp_filename = f"temp_avatar_{digital_person_id}_{int(time.time())}.jpg"
                local_avatar_path = os.path.join("app", "static", "avatars", temp_filename)
                
                from PIL import Image
                import io
                
                # 读取并处理图片
                img = Image.open(io.BytesIO(img_data))
                if img.mode != "RGB":
                    img = img.convert("RGB")
                    
                # LivePortrait 对图片要求严格，重置为 512x512
                img = img.resize((512, 512), Image.Resampling.LANCZOS)
                img.save(local_avatar_path, format="JPEG", quality=85)
            except Exception as e:
                logger.error(f"解析 Base64 头像失败: {e}")
                return
                
        if local_avatar_path and os.path.exists(local_avatar_path):
            local_audio_path = os.path.join("app", "static", "generic_speech.mp3")
            
            logger.info(f"检测到头像更新或初次生成，正在为数字人 {digital_person_id} 生成专属对话动态视频...")
            video_url = await _video_service.generate_generic_talking_head(
                user_id=user_id,
                avatar_local_path=local_avatar_path,
                audio_local_path=local_audio_path
            )
            
            # 更新到数据库，同时记录本次使用的头像 URL 用于以后比对
            await db["digital_persons"].update_one(
                {"_id": ObjectId(digital_person_id)},
                {"$set": {
                    "speaking_video_url": video_url,
                    "last_avatar_for_video": avatar_url
                }}
            )
            logger.info(f"数字人 {digital_person_id} 动态视频更新完毕: {video_url}")
            
    except Exception as e:
        logger.error(f"视频自动生成后台任务失败: {str(e)}", exc_info=True)

async def _update_conversation_summary(
    conversation_id: str,
    user_id: str,
    db
):
    """后台触发：当消息过长时自动压缩前面的对话为摘要，并存入 conversations 表中"""
    try:
        conversation = await db["conversations"].find_one({
            "_id": ObjectId(conversation_id),
            "user_id": ObjectId(user_id)
        })
        if not conversation:
            return
            
        message_count = conversation.get("message_count", 0)
        threshold = settings.history_summary_threshold
        keep = settings.recent_messages_keep
        
        if message_count > threshold:
            cursor = (
                db["messages"]
                .find({"conversation_id": ObjectId(conversation_id)})
                .sort("timestamp", 1)
            )
            all_messages = []
            async for msg in cursor:
                all_messages.append(msg)
                
            if len(all_messages) <= keep:
                return
                
            messages_to_summarize = all_messages[:-keep]
            history_text = "\n".join([f"{m['role']}: {m['content']}" for m in messages_to_summarize])
            
            exist_summary = conversation.get("summary", "")
            if exist_summary:
                history_text = f"【原有摘要】\n{exist_summary}\n\n【最新历史】\n{history_text}"
                
            new_summary = await _ai_service.summarize_history(history_text)
            
            if new_summary:
                await db["conversations"].update_one(
                    {"_id": ObjectId(conversation_id)},
                    {"$set": {"summary": new_summary}}
                )
                
                msg_ids_to_del = [m["_id"] for m in messages_to_summarize]
                if msg_ids_to_del:
                    await db["messages"].delete_many({"_id": {"$in": msg_ids_to_del}})
                
                await db["conversations"].update_one(
                    {"_id": ObjectId(conversation_id)},
                    {"$inc": {"message_count": -len(msg_ids_to_del)}}
                )
                logger.info(f"对话 {conversation_id} 摘要更新完毕，压缩了 {len(msg_ids_to_del)} 条消息")
    except Exception as e:
        logger.error(f"更新对话摘要失败: {e}", exc_info=True)

@router.post("/message", summary="发送消息")
async def send_message(
    body: SendMessageRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database),
):
    """
    发送消息并获取 AI 回复
    流程：
    1. 验证数字人归属
    2. 获取或创建对话
    3. 获取用户记忆（用于构建 prompt）
    4. 调用 AI 生成回复
    5. 保存消息到 messages 集合
    6. 后台触发记忆提取（不阻塞响应）
    """
    user_id = current_user["id"]

    # 验证并发
    semaphore = get_user_semaphore(user_id)
    if semaphore.locked():
        return error_response("您的请求太频繁，请稍候再试 (最多 2 个并发)", status_code=429)

    # 验证数字人
    if not validate_object_id(body.digital_person_id):
        return error_response("无效的数字人 ID", status_code=400)

    digital_person = await db["digital_persons"].find_one({
        "_id": ObjectId(body.digital_person_id),
        "user_id": ObjectId(user_id),
    })
    if not digital_person:
        return error_response("数字人不存在或无权限访问", status_code=404)

    # 清理用户输入
    cleaned_message = sanitize_input(body.message)
    if not cleaned_message:
        return error_response("消息内容不能为空", status_code=400)

    # 获取或创建对话
    conversation_id = body.conversation_id
    if conversation_id and validate_object_id(conversation_id):
        conversation = await db["conversations"].find_one({
            "_id": ObjectId(conversation_id),
            "user_id": ObjectId(user_id),
        })
        if not conversation:
            conversation_id = None  # 对话不存在，重新创建

    if not conversation_id:
        now = get_current_time()
        conv_doc = {
            "user_id": ObjectId(user_id),
            "digital_person_id": ObjectId(body.digital_person_id),
            "title": f"与{digital_person['name']}的对话",
            "message_count": 0,
            "last_message_at": now,
            "created_at": now,
            "updated_at": now,
        }
        result = await db["conversations"].insert_one(conv_doc)
        conversation_id = str(result.inserted_id)

    # 获取最近对话历史（用于 AI 上下文）
    # 若已有历史摘要，则只取最新 N 条（由 recent_messages_keep 控制）
    conversation_obj = None
    if conversation_id and validate_object_id(conversation_id):
        conversation_obj = await db["conversations"].find_one({"_id": ObjectId(conversation_id)})
    has_summary = bool(conversation_obj and conversation_obj.get("summary"))
    msg_limit = settings.recent_messages_keep if has_summary else 12

    recent_msgs = []
    cursor = (
        db["messages"]
        .find({"conversation_id": ObjectId(conversation_id)})
        .sort("timestamp", -1)
        .limit(msg_limit)
    )
    async for msg in cursor:
        recent_msgs.append({"role": msg["role"], "content": msg["content"]})
    recent_msgs.reverse()

    # 获取与当前用户输入最相关的记忆（向量化语义检索，top5）
    memories = await _memory_service.get_relevant_memories(
        user_id=user_id,
        digital_person_id=body.digital_person_id,
        query_text=cleaned_message,
        db=db,
        top_k=5,
    )

    # 获取用户职业档案（融入 prompt）
    user_profile = await db["user_profiles"].find_one({"user_id": ObjectId(user_id)})

    # 分析用户情感
    emotion_data = _emotion_service.analyze_emotion(cleaned_message)

    # 识别场景
    scene = _prompt_service.detect_scene(cleaned_message, emotion_data["emotion"])
    interview_knowledge = ""
    weather_info = ""
    
    if scene == "interview":
        # 组合最近历史 + 记忆，用于推断用户专业
        history_text = " ".join([m["content"] for m in recent_msgs]) + " " + cleaned_message
        major = _interview_service.detect_major(history_text, memories)
        # 检测面试阶段（面试前/中/后）
        stage = _interview_service.detect_stage(cleaned_message)
        interview_knowledge = _interview_service.get_interview_knowledge(major, stage)

    # 天气查询独立于场景——只要检测到面试出行意图就触发
    if _prompt_service.detect_interview_trip(cleaned_message) or (scene == "interview"):
        target_city = _weather_service.extract_city(cleaned_message)
        if target_city:
            try:
                w_info = await _weather_service.get_weather(target_city)
                if w_info:
                    weather_info = w_info
            except Exception as e:
                logger.warning(f"天气查询失败（降级跳过）: {e}")

    # 取出之前存储的摘要
    history_summary = conversation_obj.get("summary", "") if conversation_obj else ""

    # 构建个性化 system prompt
    system_prompt = _prompt_service.build_persona_prompt(
        digital_person=digital_person,
        memories=memories,
        recent_messages=recent_msgs,
        user_profile=user_profile,
        scene=scene,
        history_summary=history_summary,
        weather_info=weather_info,
        interview_knowledge=interview_knowledge
    )


    # 构建 AI 消息列表
    ai_messages = list(recent_msgs)
    ai_messages.append({"role": "user", "content": cleaned_message})

    print("\n" + "="*50, flush=True)
    print(f"=== [对话流] 新消息 ===", flush=True)
    print(f"数字人ID: {body.digital_person_id}", flush=True)
    print(f"用户输入: {cleaned_message}", flush=True)
    print(f"System Prompt:\n{system_prompt}", flush=True)
    print(f"=========================", flush=True)
    print("="*50 + "\n", flush=True)

    # 调用 AI 生成回复
    ai_reply = await _ai_service.chat(ai_messages, system_prompt)
    print(f"[对话流] AI 回复: {ai_reply}", flush=True)

    # 保存用户消息
    now = get_current_time()
    user_msg_doc = {
        "conversation_id": ObjectId(conversation_id),
        "role": "user",
        "content": cleaned_message,
        "emotion": emotion_data["emotion"],
        "emotion_polarity": emotion_data["polarity"],
        "timestamp": now,
    }
    await db["messages"].insert_one(user_msg_doc)

    # 保存 AI 回复
    ai_emotion = _emotion_service.analyze_emotion(ai_reply)
    ai_msg_doc = {
        "conversation_id": ObjectId(conversation_id),
        "role": "assistant",
        "content": ai_reply,
        "emotion": ai_emotion["emotion"],
        "emotion_polarity": ai_emotion["polarity"],
        "timestamp": get_current_time(),
    }
    await db["messages"].insert_one(ai_msg_doc)

    # 更新对话元数据
    await db["conversations"].update_one(
        {"_id": ObjectId(conversation_id)},
        {
            "$set": {"last_message_at": now, "updated_at": now},
            "$inc": {"message_count": 2},
        },
    )

    # 后台触发记忆提取（不阻塞响应）
    background_tasks.add_task(
        _trigger_memory_extraction,
        user_id=user_id,
        digital_person_id=body.digital_person_id,
        conversation_id=conversation_id,
        db=db,
    )
    
    # 后台触发视频动态生成（懒加载模式）
    background_tasks.add_task(
        _trigger_video_generation,
        user_id=user_id,
        digital_person_id=body.digital_person_id,
        db=db,
    )
    
    # 后台触发摘要检测
    background_tasks.add_task(
        _update_conversation_summary,
        conversation_id=conversation_id,
        user_id=user_id,
        db=db,
    )

    return success_response(
        data={
            "reply": ai_reply,
            "conversation_id": conversation_id,
            "emotion": emotion_data["emotion"],
            "emotion_polarity": emotion_data["polarity"],
            "timestamp": now.isoformat(),
        },
        message="消息发送成功",
    )


@router.post("/message/stream", summary="流式发送消息（SSE）")
async def send_message_stream(
    body: SendMessageRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database),
):
    """
    流式发送消息，通过 SSE（text/event-stream）逐块返回 AI 回复
    流程：
    1. 验证数字人归属
    2. 获取或创建对话
    3. 获取用户记忆构建 prompt
    4. 开启 AI 流式生成
    5. 边生成边返回给客户端
    6. 完成后保存消息 + 后台触发记忆提取
    """
    user_id = current_user["id"]

    semaphore = get_user_semaphore(user_id)
    if semaphore.locked():
        return error_response("您的请求太频繁，请稍候再试 (最多 2 个并发)", status_code=429)

    # 为了能进入流式，不在这里用 async with 阻塞整个响应。我们用 context manager 包装 generator

    # 验证数字人
    if not validate_object_id(body.digital_person_id):
        return error_response("无效的数字人 ID", status_code=400)

    digital_person = await db["digital_persons"].find_one({
        "_id": ObjectId(body.digital_person_id),
        "user_id": ObjectId(user_id),
    })
    if not digital_person:
        return error_response("数字人不存在或无权限访问", status_code=404)

    cleaned_message = sanitize_input(body.message)
    if not cleaned_message:
        return error_response("消息内容不能为空", status_code=400)

    # 获取或创建对话
    conversation_id = body.conversation_id
    if conversation_id and validate_object_id(conversation_id):
        conversation = await db["conversations"].find_one({
            "_id": ObjectId(conversation_id),
            "user_id": ObjectId(user_id),
        })
        if not conversation:
            conversation_id = None

    if not conversation_id:
        now = get_current_time()
        conv_doc = {
            "user_id": ObjectId(user_id),
            "digital_person_id": ObjectId(body.digital_person_id),
            "title": f"与{digital_person['name']}的对话",
            "message_count": 0,
            "last_message_at": now,
            "created_at": now,
            "updated_at": now,
        }
        result = await db["conversations"].insert_one(conv_doc)
        conversation_id = str(result.inserted_id)

    # 获取最近对话历史
    # 若已有历史摘要，则只取最新 N 条（由 recent_messages_keep 控制）
    conversation_obj = None
    if conversation_id and validate_object_id(conversation_id):
        conversation_obj = await db["conversations"].find_one({"_id": ObjectId(conversation_id)})
    has_summary = bool(conversation_obj and conversation_obj.get("summary"))
    msg_limit = settings.recent_messages_keep if has_summary else 12

    recent_msgs = []
    cursor = (
        db["messages"]
        .find({"conversation_id": ObjectId(conversation_id)})
        .sort("timestamp", -1)
        .limit(msg_limit)
    )
    async for msg in cursor:
        recent_msgs.append({"role": msg["role"], "content": msg["content"]})
    recent_msgs.reverse()

    # 获取与当前用户输入最相关的记忆（向量化语义检索，top5）
    memories = await _memory_service.get_relevant_memories(
        user_id=user_id,
        digital_person_id=body.digital_person_id,
        query_text=cleaned_message,
        db=db,
        top_k=5,
    )
    user_profile = await db["user_profiles"].find_one({"user_id": ObjectId(user_id)})

    # 分析用户情感
    emotion_data = _emotion_service.analyze_emotion(cleaned_message)

    # 识别场景
    scene = _prompt_service.detect_scene(cleaned_message, emotion_data["emotion"])
    interview_knowledge = ""
    weather_info = ""
    
    if scene == "interview":
        # 组合最近历史 + 记忆，用于推断用户专业
        history_text = " ".join([m["content"] for m in recent_msgs]) + " " + cleaned_message
        major = _interview_service.detect_major(history_text, memories)
        # 检测面试阶段（面试前/中/后）
        stage = _interview_service.detect_stage(cleaned_message)
        interview_knowledge = _interview_service.get_interview_knowledge(major, stage)

    # 天气查询独立于场景——只要检测到面试出行意图就触发
    if _prompt_service.detect_interview_trip(cleaned_message) or (scene == "interview"):
        target_city = _weather_service.extract_city(cleaned_message)
        if target_city:
            try:
                w_info = await _weather_service.get_weather(target_city)
                if w_info:
                    weather_info = w_info
            except Exception as e:
                logger.warning(f"天气查询失败（降级跳过）: {e}")

    # 取出之前存储的摘要
    history_summary = conversation_obj.get("summary", "") if conversation_obj else ""

    # 构建 system prompt
    system_prompt = _prompt_service.build_persona_prompt(
        digital_person=digital_person,
        memories=memories,
        recent_messages=recent_msgs,
        user_profile=user_profile,
        scene=scene,
        history_summary=history_summary,
        weather_info=weather_info,
        interview_knowledge=interview_knowledge
    )

    # 构建 AI 消息列表
    ai_messages = list(recent_msgs)
    ai_messages.append({"role": "user", "content": cleaned_message})

    # 先保存用户消息
    now = get_current_time()
    user_msg_doc = {
        "conversation_id": ObjectId(conversation_id),
        "role": "user",
        "content": cleaned_message,
        "emotion": emotion_data["emotion"],
        "emotion_polarity": emotion_data["polarity"],
        "timestamp": now,
    }
    await db["messages"].insert_one(user_msg_doc)

    async def event_generator() -> AsyncGenerator[str, None]:
        """SSE 事件生成器，逐块返回 AI 回复文本"""
        # 进入流时正式获取信号量
        await semaphore.acquire()
        try:
            full_reply = []
            
            meta_payload = {
                "conversation_id": conversation_id,
                "emotion": emotion_data["emotion"],
                "emotion_polarity": emotion_data["polarity"],
                "scene": scene  # 透传场景给前端，激活特殊 UI
            }
            if scene == "interview":
                meta_payload["interview_tips"] = _interview_service.get_interview_tips_array()
            if scene == "crisis":
                meta_payload["hotlines"] = ["北京: 010-82951332", "全国: 400-161-9995"]
            if weather_info:
                meta_payload["weather_info"] = weather_info  # 透传天气数据供前端渲染天气卡片

            # 先发送 conversation_id 供客户端续接
            meta_start = json.dumps({"meta_start": meta_payload}, ensure_ascii=False)
            yield f"data: {meta_start}\n\n"

            # 流式输出 AI 回复
            async for chunk_text in _ai_service.chat_stream(ai_messages, system_prompt):
                full_reply.append(chunk_text)
                chunk_json = json.dumps({"chunk": chunk_text}, ensure_ascii=False)
                yield f"data: {chunk_json}\n\n"

            # 所有 chunk 发完后，保存 AI 回复并返回 done 信号
            ai_reply = "".join(full_reply)
            ai_emotion = _emotion_service.analyze_emotion(ai_reply)
            ai_msg_doc = {
                "conversation_id": ObjectId(conversation_id),
                "role": "assistant",
                "content": ai_reply,
                "emotion": ai_emotion["emotion"],
                "emotion_polarity": ai_emotion["polarity"],
                "timestamp": get_current_time(),
            }
            await db["messages"].insert_one(ai_msg_doc)

            # 更新对话元数据
            t_now = get_current_time()
            await db["conversations"].update_one(
                {"_id": ObjectId(conversation_id)},
                {
                    "$set": {"last_message_at": t_now, "updated_at": t_now},
                    "$inc": {"message_count": 2},
                },
            )

            # 危机场景：流结束后额外推送 crisis 帧，触发前端弹窗
            if scene == "crisis":
                crisis_json = json.dumps({
                    "type": "crisis",
                    "hotlines": ["北京: 010-82951332", "全国: 400-161-9995"],
                    "message": "如果你正在经历痛苦，请记住你并不孤单。以下是专业心理援助热线，随时可以拨打。"
                }, ensure_ascii=False)
                yield f"data: {crisis_json}\n\n"

            # 结束标志（附带最终情感数据）
            done_json = json.dumps({
                "done": True,
                "emotion": ai_emotion["emotion"],
                "timestamp": t_now.isoformat(),
            }, ensure_ascii=False)
            yield f"data: {done_json}\n\n"

            # 后台触发记忆提取
            asyncio.ensure_future(_trigger_memory_extraction(
                user_id=user_id,
                digital_person_id=body.digital_person_id,
                conversation_id=conversation_id,
                db=db,
            ))
            # 后台触发视频生成
            asyncio.ensure_future(_trigger_video_generation(
                user_id=user_id,
                digital_person_id=body.digital_person_id,
                db=db,
            ))
            # 后台触发摘要检测
            asyncio.ensure_future(_update_conversation_summary(
                conversation_id=conversation_id,
                user_id=user_id,
                db=db,
            ))

        except Exception as e:
            logger.error(f"流式响应生成异常: {e}", exc_info=True)
            err_json = json.dumps({"error": "AI 服务出错，请重试"}, ensure_ascii=False)
            yield f"data: {err_json}\n\n"
        finally:
            semaphore.release()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/", summary="获取当前用户的对话列表")
async def list_conversations(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database),
):
    """获取当前用户的所有对话（按最后更新时间降序）"""
    conversations = []
    cursor = (
        db["conversations"]
        .find({"user_id": ObjectId(current_user["id"])})
        .sort("updated_at", -1)
        .limit(50)
    )

    async for conv in cursor:
        conversations.append({
            "id": str(conv["_id"]),
            "digital_person_id": str(conv["digital_person_id"]),
            "title": conv.get("title", "对话"),
            "message_count": conv.get("message_count", 0),
            "last_message_at": conv["last_message_at"].isoformat()
            if isinstance(conv.get("last_message_at"), datetime)
            else conv.get("last_message_at"),
            "created_at": conv["created_at"].isoformat()
            if isinstance(conv.get("created_at"), datetime)
            else conv.get("created_at"),
        })

    return success_response(data=conversations)


@router.get("/{conversation_id}", summary="获取对话详情及消息历史")
async def get_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database),
):
    """获取指定对话的详情和消息历史"""
    if not validate_object_id(conversation_id):
        return error_response("无效的对话 ID", status_code=400)

    conversation = await db["conversations"].find_one({
        "_id": ObjectId(conversation_id),
        "user_id": ObjectId(current_user["id"]),
    })
    if not conversation:
        return error_response("对话不存在", status_code=404)

    # 获取消息列表
    messages = []
    
    if conversation.get("summary"):
        messages.append({
            "id": "summary_msg",
            "role": "system",
            "content": f"【前情提要】\n{conversation['summary']}",
            "emotion": "平静",
            "emotion_polarity": "neutral",
            "timestamp": conversation["created_at"].isoformat() if isinstance(conversation.get("created_at"), datetime) else conversation.get("created_at"),
        })

    cursor = (
        db["messages"]
        .find({"conversation_id": ObjectId(conversation_id)})
        .sort("timestamp", -1)
        .limit(getattr(settings, 'recent_messages_keep', 8))
    )
    raw_msgs = []
    async for msg in cursor:
        raw_msgs.append(msg)
    raw_msgs.reverse()

    for msg in raw_msgs:
        messages.append({
            "id": str(msg["_id"]),
            "role": msg["role"],
            "content": msg["content"],
            "emotion": msg.get("emotion", "平静"),
            "emotion_polarity": msg.get("emotion_polarity", "neutral"),
            "timestamp": msg["timestamp"].isoformat()
            if isinstance(msg.get("timestamp"), datetime)
            else msg.get("timestamp"),
        })

    return success_response(data={
        "id": str(conversation["_id"]),
        "digital_person_id": str(conversation["digital_person_id"]),
        "title": conversation.get("title", "对话"),
        "message_count": conversation.get("message_count", 0),
        "messages": messages,
        "created_at": conversation["created_at"].isoformat()
        if isinstance(conversation.get("created_at"), datetime)
        else conversation.get("created_at"),
    })


@router.delete("/{conversation_id}", summary="删除对话")
async def delete_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_database),
):
    """删除对话及其所有消息"""
    if not validate_object_id(conversation_id):
        return error_response("无效的对话 ID", status_code=400)

    result = await db["conversations"].delete_one({
        "_id": ObjectId(conversation_id),
        "user_id": ObjectId(current_user["id"]),
    })
    if result.deleted_count == 0:
        return error_response("对话不存在", status_code=404)

    # 删除关联消息
    await db["messages"].delete_many({"conversation_id": ObjectId(conversation_id)})

    return success_response(message="对话已删除")